"""
main.py — hammasini birlashtiruvchi asosiy fayl.

Ishlash mantig'i (har POLL_INTERVAL_SECONDS da takrorlanadi):
  1) BITTA so'rov bilan Smartup'dan "Отгружен" (B#S) orderlarni oladi
  2) Har bir orderni filial_id+subfilial_code bo'yicha kerakli kompaniyaga ajratadi
  3) Avval yuborilmagan orderlarni tanlaydi (takror yubormaslik uchun)
  4) Har biri uchun Спецификация Excel yasaydi
  5) O'sha kompaniyaning Telegram guruhiga yuboradi
  6) Yuborilgan order ID sini `sent_deals.json` ga yozib qo'yadi

Ishga tushirish:  python main.py
To'xtatish:        Ctrl + C
"""

import json
import os
import time
import traceback
from datetime import datetime, timedelta

import config
from smartup_client import fetch_all_orders, fetch_person_details
from excel_builder import build_spec
from telegram_sender import send_excel

STATE_FILE = os.path.join(os.path.dirname(__file__), "sent_deals.json")
CLIENTS_CACHE_FILE = os.path.join(os.path.dirname(__file__), "clients_cache.json")


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
    if pid in clients:
        return clients[pid]
    try:
        buyer = fetch_person_details(pid)
    except Exception as e:
        print(f"[mijoz {pid} olishda xato]: {e}")
        return None
    if buyer:
        clients[pid] = buyer
        save_clients(clients)
    return buyer


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
    """Order qaysi ombor(lar)ga tegishli — tovarlardagi warehouse_code to'plami."""
    codes = set()
    for it in order.get("order_products", []) or []:
        wc = it.get("warehouse_code")
        if wc:
            codes.add(str(wc).strip())
    return codes


def _is_excluded_warehouse(order: dict) -> bool:
    """Order tarkibida BIRORTA ham chetlatilgan (Терминал) ombor bo'lsa True.
    Har filialning o'z Терминал kodi bor (BP Pharma=119835, ...). Buyurtmada
    hatto bitta Терминал tovar bo'lsa ham butun buyurtma yuborilmaydi."""
    excluded = set(getattr(config, "EXCLUDE_WAREHOUSE_CODES", []) or [])
    if not excluded:
        return False
    codes = _order_warehouse_codes(order)
    # Kesishma bo'sh bo'lmasa — chetlatilgan ombor bor, yubormaymiz.
    return bool(codes & excluded)


def run_once(sent: set, clients: dict) -> None:
    # Oxirgi 1 kun oralig'ini so'raymiz (Smartup 7 kungacha ruxsat beradi)
    now = datetime.now()
    date_to = now.strftime("%d.%m.%Y")
    date_from = (now - timedelta(days=1)).strftime("%d.%m.%Y")

    # BITTA so'rov — hamma kompaniya uchun.
    try:
        orders = fetch_all_orders(date_from, date_to)
    except Exception as e:
        print(f"Smartup so'rovda xato: {e}")
        return

    for company in config.COMPANIES:
        company_orders = [o for o in orders if order_belongs(o, company)]

        # Ombor filtri: "Терминал" (config'dagi kodlar) orderlarini yubormaymiz.
        before = len(company_orders)
        company_orders = [o for o in company_orders if not _is_excluded_warehouse(o)]
        skipped = before - len(company_orders)
        if skipped:
            print(f"[{company['name']}] {skipped} ta order ombor bo'yicha "
                  f"chetlatildi (Терминал).")

        for deal in company_orders:
            key = deal_key(company, deal)
            if key in sent:
                continue  # allaqachon yuborilgan
            try:
                buyer = get_buyer(deal, clients)  # mijoz bank ma'lumoti (keshlangan)
                path = build_spec(deal, company, buyer)
                shtat = (deal.get("sales_manager_name") or "").strip()  # UI "Штат" ustuni
                caption = f'{company["name"]} — {shtat}' if shtat else company["name"]
                send_excel(company["telegram_chat"], path, caption)
                sent.add(key)
                save_sent(sent)
                print(f"[OK] {key} yuborildi")
                os.remove(path)
            except Exception as e:
                print(f"[XATO] {key}: {e}")
                traceback.print_exc()


def main():
    print("Smartup -> Telegram bot ishga tushdi. Ctrl+C bilan to'xtating.")
    sent = load_sent()
    clients = load_clients()
    while True:
        try:
            run_once(sent, clients)
        except Exception as e:
            print(f"Umumiy xato: {e}")
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
