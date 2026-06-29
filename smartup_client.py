"""
smartup_client.py — Smartup API bilan gaplashadigan qism.

Endpoint:  POST {BASE}/b/trade/txs/tdeal/order$export
Auth:      Basic Auth (login/parol)
Header:    project_code (filial_id BO'SH bo'lishi shart — aks holda 401!)

MUHIM kashfiyotlar (haqiqiy hisobda tekshirilgan):
  - Header'da filial_id ga qiymat qo'yilsa -> 401 "Требуется авторизация".
    Shuning uchun filial_id BO'SH yuboriladi va HAMMA filial qaytadi.
  - Body'da filial_code yuborilsa -> 400. Shuning uchun filial_code YUBORILMAYDI.
  - statuses filtri faqat HARF kodlarini qabul qiladi ("B#S" = Отгружен).
  - Javob bosh kaliti: "order".
Kompaniyalarga ajratish main.py'da, javobdagi filial_id+subfilial_code bo'yicha.
"""

import requests
from requests.auth import HTTPBasicAuth
import config


ENDPOINT = "/b/trade/txs/tdeal/order$export"
LEGAL_PERSON_ENDPOINT = "/b/anor/mxsx/mr/legal_person$export"


def _headers() -> dict:
    return {
        "project_code": config.SMARTUP_PROJECT_CODE,
        "filial_id": "",  # BO'SH bo'lishi shart (aks holda 401)
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(config.SMARTUP_USERNAME, config.SMARTUP_PASSWORD)


def fetch_legal_person(person_code: str) -> dict | None:
    """Mijoz (yuridik shaxs) ma'lumotlarini `code` (order'dagi person_code)
    bo'yicha oladi: tin, vat_code, main_phone, address, bank_accounts (Р/с, МФО).
    Topilmasa None. ESLATMA: References limiti 100/kun — main.py'da keshlanadi."""
    if not person_code:
        return None
    url = config.SMARTUP_BASE_URL + LEGAL_PERSON_ENDPOINT
    body = {"code": str(person_code)}
    resp = requests.post(url, json=body, headers=_headers(), auth=_auth(), timeout=60)
    resp.raise_for_status()
    items = resp.json().get("legal_person", []) or []
    return items[0] if items else None


def fetch_all_orders(date_from: str, date_to: str) -> list[dict]:
    """Berilgan sana oralig'idagi kerakli statusdagi BARCHA orderlarni oladi.
    Bitta so'rov — 3 kompaniya uchun ham (keyin kod ichida ajratiladi).
    date_from / date_to — "dd.mm.yyyy" formatida."""
    url = config.SMARTUP_BASE_URL + ENDPOINT
    headers = {
        "project_code": config.SMARTUP_PROJECT_CODE,
        "filial_id": "",  # BO'SH bo'lishi shart (aks holda 401)
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "statuses": config.TARGET_STATUSES,   # masalan ["B#S"] = Отгружен
        "begin_modified_on": date_from,
        "end_modified_on": date_to,
    }
    auth = HTTPBasicAuth(config.SMARTUP_USERNAME, config.SMARTUP_PASSWORD)

    resp = requests.post(url, json=body, headers=headers, auth=auth, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    orders = data.get("order", [])

    # Xavfsizlik uchun statusni kod ichida ham tekshiramiz (server filtri yetarli,
    # lekin TARGET_STATUSES bo'sh bo'lsa hammasi o'tadi).
    if config.TARGET_STATUSES:
        orders = [o for o in orders
                  if (o.get("status") or "").strip() in config.TARGET_STATUSES]
    return orders
