"""
main.py — hammasini birlashtiruvchi asosiy fayl.

Ishlash mantig'i (har POLL_INTERVAL_SECONDS da takrorlanadi):
  1) BITTA so'rov bilan Smartup'dan FAQAT "В ожидании" (B#W) orderlarni oladi
  2) Har bir orderni filial_id+subfilial_code bo'yicha kerakli kompaniyaga ajratadi
  3) Yangi ko'rilganlarini NAVBATGA yozadi (`pending_deals.json`)
  4) Navbatdagi har biri uchun Спецификация Excel yasaydi
  5) O'sha kompaniyaning Telegram guruhiga yuboradi
  6) Yuborilganini navbatdan chiqarib, `sent_deals.json` ga yozib qo'yadi

Nega navbat kerak: bot orderni faqat "В ожидании" paytida ko'radi, lekin
yuborish o'sha zahoti muvaffaqiyatsiz bo'lishi mumkin (Telegram xatosi, bot
qayta ishga tushishi, Smartup limiti). Navbat bo'lmasa order keyingi
tekshiruvgacha boshqa statusga o'tib ketadi va butunlay yo'qoladi. Navbatga
tushgan order esa statusi o'zgargan bo'lsa ham yuborilaveradi.

Ishga tushirish:  python main.py
To'xtatish:        Ctrl + C
"""

import json
import os
import time
import traceback
from datetime import datetime, timedelta

import config
import smartup_client
from smartup_client import fetch_all_orders, fetch_person_details
from excel_builder import build_spec
from telegram_sender import send_excel

# Holat fayllari joyi. Docker'da STATE_DIR=/app/data qilib volume'ga
# ulanadi — shunда konteyner qayta qurilса ham sent_deals saqlanib qoladi.
DATA_DIR = os.getenv("STATE_DIR") or os.path.dirname(__file__)
os.makedirs(DATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(DATA_DIR, "sent_deals.json")
# Ketma-ket yuborishlar orasidagi pauza (Telegram tezlik chegarasi uchun).
SEND_PAUSE_SECONDS = 3
CLIENTS_CACHE_FILE = os.path.join(DATA_DIR, "clients_cache.json")
# "В ожидании" da KO'RILGAN, lekin hali yuborilmagan orderlar navbati.
# Order shu statusdan chiqib ketsa ham navbatda qoladi va yuboriladi.
PENDING_FILE = os.path.join(DATA_DIR, "pending_deals.json")
# Doimiy log. `docker logs` tarixi konteyner qayta qurilganda YO'QOLADI —
# "bu order qachon va nega yuborilgan?" degan savolga javob topib bo'lmay
# qoladi. Shuning uchun log volume'dagi faylga ham yoziladi.
LOG_FILE = os.path.join(DATA_DIR, "bot.log")
# Kunlik limitdan shuncha so'rov zaxira qoldiriladi (mijoz kartasini olish
# kabi qo'shimcha so'rovlar uchun).
LIMIT_RESERVE = 20
# Interval qancha cho'zilsa ham shundan oshmaydi.
MAX_INTERVAL_SECONDS = 1800


def log(msg: str) -> None:
    """Xabarni ekranga va DATA_DIR/bot.log ga vaqt tamg'asi bilan yozadi."""
    line = f"{datetime.now():%d.%m.%Y %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # log yozilmasa ham bot ishlashda davom etsin


def load_pending() -> dict:
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_pending(pending: dict) -> None:
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)


def load_sent() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_sent(sent: set) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(sent), f, ensure_ascii=False, indent=2)


def load_clients() -> dict:
    """Mijozlar keshi: {person_id: {karta ma'lumoti}}. person_id bo'yicha keshlanadi,
    shu bilan bitta mijoz uchun API'ga qayta-qayta murojaat qilinmaydi."""
    if os.path.exists(CLIENTS_CACHE_FILE):
        with open(CLIENTS_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_clients(clients: dict) -> None:
    with open(CLIENTS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(clients, f, ensure_ascii=False, indent=2)


def get_buyer(deal: dict, clients: dict) -> dict:
    """Order'dagi `person_id` bo'yicha mijoz kartasini (bank/tel/manzil) oladi.
    Kartani `legal_person_view:model` beradi — org doirasidan qat'i nazar,
    uchala kompaniya (Gynomedix/BP/Bromedix) mijozlari uchun ham ishlaydi.
    Natija person_id bo'yicha keshlanadi."""
    pid = str(deal.get("person_id") or "").strip()
    if not pid:
        return None
    cached = clients.get(pid)
    # Bank ma'lumoti TO'LIQ bo'lsa keshdan olamiz. Bo'sh bo'lsa (menejer
    # mijoz kartasiga bankни hali kiritmagan) — har safar qayta so'raymiz,
    # keyin to'ldirilsa avtomatik olinadi.
    if cached and cached.get("bank_accounts"):
        return cached
    try:
        buyer = fetch_person_details(pid)
    except Exception as e:
        log(f"[mijoz {pid} olishda xato]: {e}")
        return cached
    if buyer and buyer.get("bank_accounts"):
        clients[pid] = buyer  # faqat to'liq ma'lumotni keshlaymiz
        save_clients(clients)
    return buyer or cached


def deal_key(company: dict, deal: dict) -> str:
    did = deal.get("deal_id") or deal.get("id") or ""
    return f'{company["name"]}:{did}'


def order_belongs(order: dict, company: dict) -> bool:
    """Order shu kompaniyaga tegishlimi — filial_id (+subfilial_code) bo'yicha.
    subfilial_code berilmagan bo'lsa, o'sha filialdagi barcha order tegishli."""
    if str(order.get("filial_id") or "") != str(company.get("filial_id") or ""):
        return False
    sub = (company.get("subfilial_code") or "").strip()
    if sub:  # subfilial ko'rsatilgan bo'lsa — aniq mos kelishi shart
        return str(order.get("subfilial_code") or "") == sub
    return True


def _order_warehouse_codes(order: dict) -> set:
    """Order qaysi ombor(lar)ga tegishli — tovarlardagi warehouse_code to'plami.
    Probnik orderlarda tovarlar `order_products` emas, `order_gifts` ichida
    keladi — shuning uchun uchala ro'yxat ham tekshiriladi."""
    codes = set()
    for key in ("order_products", "order_gifts", "order_consignments"):
        for it in order.get(key, []) or []:
            wc = it.get("warehouse_code")
            if wc:
                codes.add(str(wc).strip())
    return codes


def _is_excluded_warehouse(order: dict) -> bool:
    """Order tarkibida BIRORTA ham Терминал ombor bo'lsa True — bunday order
    umuman yuborilmaydi (summasi qancha bo'lishidan qat'i nazar).
    Kodlar `.env` dagi EXCLUDE_WAREHOUSE_CODES da (har filialning o'ziniki)."""
    excluded = set(getattr(config, "EXCLUDE_WAREHOUSE_CODES", []) or [])
    if not excluded:
        return False
    return bool(_order_warehouse_codes(order) & excluded)


def _is_sample_order(order: dict) -> bool:
    """Probnik (bepul namuna) orderimi. Belgisi: pullik tovar qatori
    (`order_products`) umuman yo'q — hamma narsa `order_gifts` ichida va
    jami summa 0. Терминал filtri tutmay qolgan probniklar uchun qo'shimcha
    himoya (masalan probnik boshqa ombordan berilgan bo'lsa)."""
    if order.get("order_products"):
        return False
    try:
        total = float(order.get("total_amount") or 0)
    except (TypeError, ValueError):
        total = 0.0
    return total == 0


def _skip_reason(order: dict) -> str | None:
    """Order nega yuborilmaydi — sabab matni, yuborilsa None."""
    if _is_excluded_warehouse(order):
        return "Терминал ombor"
    if _is_sample_order(order):
        return "probnik (summa 0)"
    return None


def collect_pending(orders: list, sent: set, pending: dict) -> int:
    """"В ожидании" da ko'rilgan orderlarni navbatga yozadi.

    Order shu lahzada yuborilmasa ham (Telegram xatosi, bot o'chib qolishi,
    Smartup limiti) navbatda saqlanadi — keyin, order allaqachon boshqa
    statusga o'tib ketgan bo'lsa ham, yuboriladi. Navbatga faqat В ожидании
    paytida ko'rilgan orderlar tushadi."""
    # Hech bir kompaniyaga tegishli bo'lmagan orderlar (odatda menejer Smartup'da
    # "Проект"ni ko'rsatmagan — subfilial_code bo'sh). Jimgina yo'qolib ketmasin.
    for o in orders:
        if _skip_reason(o):
            continue
        if not any(order_belongs(o, c) for c in config.COMPANIES):
            log(f"[DIQQAT] order {o.get('deal_id')} hech bir kompaniyaga "
                  f"tushmadi (filial={o.get('filial_id')}, "
                  f"subfilial={o.get('subfilial_code')}) — Smartup'da "
                  f"\"Проект\" ko'rsatilmagan bo'lishi mumkin.")

    yangi = 0
    for company in config.COMPANIES:
        for o in orders:
            if not order_belongs(o, company):
                continue
            reason = _skip_reason(o)
            if reason:
                log(f"[{company['name']}] order {o.get('deal_id')} "
                      f"chetlatildi — {reason}.")
                continue
            key = deal_key(company, o)
            if key in sent or key in pending:
                continue  # yuborilgan yoki allaqachon navbatda
            pending[key] = {
                "company": company["name"],
                "order": o,
                "seen_on": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            }
            yangi += 1
            # Statusni ham yozamiz: order В ожидании da ko'rilganmi yoki
            # allaqachon Отгружен ga o'tib ketganda quvib yetilganmi —
            # keyin faqat shu satrdan bilinadi (API status tarixini bermaydi).
            log(f"[NAVBAT] {key} navbatga olindi "
                f"(status {o.get('status')}).")
    if yangi:
        save_pending(pending)
    return yangi


def send_pending(sent: set, clients: dict, pending: dict) -> None:
    """Navbatdagi orderlarni yuboradi. Yuborilgani navbatdan chiqadi,
    xato bo'lgani navbatda qoladi va keyingi aylanishda qayta uriniladi."""
    companies = {c["name"]: c for c in config.COMPANIES}
    for key, item in list(pending.items()):
        company = companies.get(item.get("company"))
        deal = item.get("order") or {}
        if not company:
            log(f"[XATO] {key}: '{item.get('company')}' kompaniyasi "
                  f"config'da yo'q, navbatdan olib tashlandi.")
            pending.pop(key, None)
            save_pending(pending)
            continue
        if key in sent:  # ehtiyot chorasi
            pending.pop(key, None)
            save_pending(pending)
            continue
        try:
            buyer = get_buyer(deal, clients)  # mijoz bank ma'lumoti (keshlangan)
            path = build_spec(deal, company, buyer)
            shtat = (deal.get("sales_manager_name") or "").strip()  # UI "Штат" ustuni
            mijoz = ((buyer or {}).get("name")
                     or deal.get("person_name") or "").strip()  # Покупатель
            # Caption: "Kompaniya — Штат — Mijoz" (bo'sh qismlar tushib qoladi)
            parts = [company["name"]]
            if shtat:
                parts.append(shtat)
            if mijoz:
                parts.append(mijoz)
            caption = " — ".join(parts)
            send_excel(company["telegram_chat"], path, caption)
            sent.add(key)
            save_sent(sent)
            pending.pop(key, None)
            save_pending(pending)
            # chat_id ni ham yozamiz: `.env` da guruh kodi almashsa, hujjat
            # "yuborildi" deb belgilanadi-yu eski guruhga ketadi. Keyin
            # "qayerga ketdi?" degan savolga javob faqat shu satrdan topiladi.
            log(f"[OK] {key} yuborildi -> chat {company['telegram_chat']}")
            os.remove(path)
            # Telegram bitta guruhga daqiqasiga ~20 ta xabarga ruxsat beradi.
            # Navbat to'planib qolганda chegaraga urilmaslik uchun pauza.
            time.sleep(SEND_PAUSE_SECONDS)
        except Exception as e:
            # Navbatda qoladi — keyingi aylanishda qayta uriniladi.
            log(f"[XATO] {key}: {e} (navbatda qoldi, qayta uriniladi)")
            traceback.print_exc()


def run_once(sent: set, clients: dict, pending: dict) -> None:
    # Oxirgi 1 kun oralig'ini so'raymiz (Smartup 7 kungacha ruxsat beradi)
    now = datetime.now()
    date_to = now.strftime("%d.%m.%Y")
    date_from = (now - timedelta(days=1)).strftime("%d.%m.%Y")

    # BITTA so'rov — hamma kompaniya uchun.
    try:
        orders = fetch_all_orders(date_from, date_to)
        collect_pending(orders, sent, pending)
    except Exception as e:
        # So'rov muvaffaqiyatsiz bo'lsa ham navbatni yuborishga harakat
        # qilamiz — ilgari ko'rilgan orderlar yo'qolib ketmasin.
        log(f"Smartup so'rovda xato: {e}")

    send_pending(sent, clients, pending)


def next_interval() -> int:
    """Keyingi tekshiruvgacha necha soniya kutish kerakligini hisoblaydi.

    Smartup kunlik limiti (500) BUTUN hisobga tegishli — bot bilan birga
    boshqa dasturlar ham undan yeydi. Qat'iy 300s da limit kechqurun tugab
    qoladi va bot yarim tungacha KO'R bo'ladi: o'sha oynada "В ожидании" ga
    tushib keyin boshqa statusga o'tgan orderlar butunlay yo'qoladi.

    Shuning uchun qolgan so'rovlarni yarim tungacha teng taqsimlaymiz:
    interval hech qachon sozlamadagidan kichik bo'lmaydi, lekin limit
    kamayganda o'zi cho'ziladi. Limit har kuni yarim tunda tiklanadi."""
    base = config.POLL_INTERVAL_SECONDS
    left = smartup_client.LAST_LIMITS.get("left")
    if not left:  # hali javob olinmagan yoki limit ma'lum emas
        return base
    now = datetime.now()
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    seconds_left = (midnight - now).total_seconds()
    usable = max(1, left - LIMIT_RESERVE)
    needed = int(seconds_left / usable)
    interval = max(base, min(needed, MAX_INTERVAL_SECONDS))
    if interval > base:
        log(f"[LIMIT] {left} ta so'rov qoldi — tekshiruv oralig'i "
            f"{interval}s ga cho'zildi (yarim tungacha yetishi uchun).")
    return interval


def main():
    log("Smartup -> Telegram bot ishga tushdi. Ctrl+C bilan to'xtating.")
    # Amaldagi sozlamalar loglarda ko'rinib tursin — noto'g'ri .env darrov
    # bilinadi (ilgari Терминал kodlari .env dan tushib qolgan edi).
    log(f"Sozlamalar: status={config.TARGET_STATUSES}, "
          f"Терминал omborlar={config.EXCLUDE_WAREHOUSE_CODES}, "
          f"tekshiruv={config.POLL_INTERVAL_SECONDS}s")
    if not config.EXCLUDE_WAREHOUSE_CODES:
        log("[OGOHLANTIRISH] Терминал ombor kodlari bo'sh — Терминал "
              "orderlari ham guruhga yuboriladi!")
    sent = load_sent()
    clients = load_clients()
    pending = load_pending()
    if pending:
        log(f"Navbatda {len(pending)} ta yuborilmagan order bor — "
              f"ular birinchi aylanishda yuboriladi.")
    while True:
        try:
            run_once(sent, clients, pending)
        except Exception as e:
            log(f"Umumiy xato: {e}")
        time.sleep(next_interval())


if __name__ == "__main__":
    main()
