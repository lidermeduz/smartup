"""
main.py — hammasini birlashtiruvchi asosiy fayl.

Ishlash mantig'i (har POLL_INTERVAL_SECONDS da takrorlanadi):
  1) Har 3 tashkilot bo'yicha Smartup'dan "to delivered" deal'larni oladi
  2) Avval yuborilmagan deal'larni tanlaydi (takror yubormaslik uchun)
  3) Har biri uchun Спецификация Excel yasaydi
  4) O'sha tashkilotning Telegram guruhiga yuboradi
  5) Yuborilgan deal ID sini `sent_deals.json` ga yozib qo'yadi

Ishga tushirish:  python main.py
To'xtatish:        Ctrl + C
"""

import json
import os
import time
import traceback
from datetime import datetime, timedelta

import config
from smartup_client import fetch_deals
from excel_builder import build_spec
from telegram_sender import send_excel

STATE_FILE = os.path.join(os.path.dirname(__file__), "sent_deals.json")


def load_sent() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_sent(sent: set) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(sent), f, ensure_ascii=False, indent=2)


def deal_key(company: dict, deal: dict) -> str:
    did = deal.get("deal_id") or deal.get("id") or ""
    return f'{company["name"]}:{did}'


def _order_warehouse_codes(order: dict) -> set:
    """Order qaysi ombor(lar)ga tegishli — kodlar to'plamini qaytaradi.
    Avval order darajasidagi maydonni, bo'lmasa tovarlardagini tekshiradi."""
    # ehtimoliy order-darajasidagi nomlar:
    for k in ("warehouse_code", "warehouse", "ombor_code"):
        if order.get(k):
            return {str(order[k]).strip()}
    # bo'lmasa — tovarlardan yig'amiz:
    codes = set()
    for it in order.get("order_products", []) or []:
        wc = it.get("warehouse_code")
        if wc:
            codes.add(str(wc).strip())
    return codes


def _is_excluded_warehouse(order: dict) -> bool:
    """Order TO'LIQ chetlatilgan ombor(lar)dan bo'lsa True qaytaradi."""
    excluded = set(getattr(config, "EXCLUDE_WAREHOUSE_CODES", []) or [])
    if not excluded:
        return False
    codes = _order_warehouse_codes(order)
    if not codes:
        return False
    # Barcha tovarlar chetlatilgan ombordan bo'lsagina yubormaymiz
    # (aralash bo'lsa — yuboriladi; kerak bo'lsa bu shartni o'zgartiring).
    return codes.issubset(excluded)


def run_once(sent: set) -> None:
    # Oxirgi 1 kun oralig'ini so'raymiz (Smartup 7 kungacha ruxsat beradi)
    now = datetime.now()
    date_to = now.strftime("%d.%m.%Y")
    date_from = (now - timedelta(days=1)).strftime("%d.%m.%Y")

    for company in config.COMPANIES:
        try:
            deals = fetch_deals(company, date_from, date_to)
        except Exception as e:
            print(f"[{company['name']}] Smartup so'rovda xato: {e}")
            continue

        # exclude_producer_codes: BP Pharma'dan Bromedix order'larini olib tashlash.
        # ESLATMA: bu bitta order BITTA producer'ga tegishli deb hisoblaydi.
        # Agar bir order'da BP va Bromedix tovarlari ARALASH bo'lsa, bu logikani
        # qayta ko'rib chiqish kerak.
        excl = company.get("exclude_producer_codes")
        if excl:
            try:
                excluded = fetch_deals(company, date_from, date_to,
                                       producer_codes=excl)
                excluded_ids = {e.get("deal_id") for e in excluded}
                deals = [d for d in deals if d.get("deal_id") not in excluded_ids]
            except Exception as e:
                print(f"[{company['name']}] exclude filtrda xato: {e}")

        # Ombor filtri: "Терминал" (config'dagi kodlar) order'larini yubormaymiz.
        before = len(deals)
        deals = [d for d in deals if not _is_excluded_warehouse(d)]
        skipped = before - len(deals)
        if skipped:
            print(f"[{company['name']}] {skipped} ta order ombor bo'yicha "
                  f"chetlatildi (Терминал).")

        for deal in deals:
            key = deal_key(company, deal)
            if key in sent:
                continue  # allaqachon yuborilgan
            try:
                path = build_spec(deal, company)
                caption = f'{company["name"]} — yangi yetkazma (Спецификация)'
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
    while True:
        try:
            run_once(sent)
        except Exception as e:
            print(f"Umumiy xato: {e}")
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
