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
# Mijoz kartasi (bank/tel/manzil) — web UI shu endpointdan oladi. Order'dagi
# `person_id` bo'yicha ISTALGAN mijozni org doirasidan qat'i nazar qaytaradi
# (legal_person$export faqat bitta org'ni ko'radi, bu esa hammasini).
PERSON_VIEW_ENDPOINT = "/b/anor/mr/person/legal_person_view:model"
# Jismoniy shaxs (физлицо) kartasi. Ba'zi mijozlar Smartup'da yuridik emas,
# jismoniy shaxs sifatida kiritilgan — ular uchun legal_person_view 500
# "no_data_found" qaytaradi, karta shu endpointdan olinadi (INN/bank bo'lmaydi).
NATURAL_PERSON_VIEW_ENDPOINT = "/b/anor/mr/person/natural_person_view:model"


def _unwrap(text: str):
    """Smartup javobi `["(^_^)", model, data, ...]` ko'rinishida.
    Ma'lumot (data) 3-elementда (index 2). Uni qaytaradi."""
    import json
    arr = json.loads(text)
    if isinstance(arr, list) and len(arr) > 2 and isinstance(arr[2], dict):
        return arr[2]
    return {}


def _view_headers() -> dict:
    return {
        "project_code": config.SMARTUP_PROJECT_CODE,
        "filial_id": "",
        "company_id": config.SMARTUP_COMPANY_ID,
        "lang_code": "ru",
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
    }


def fetch_natural_person_details(person_id: str) -> dict | None:
    """Jismoniy shaxs (физлицо) kartasini oladi. `fetch_person_details` bilan
    bir xil shaklda qaytaradi — INN/bank jismoniy shaxsda bo'lmaydi, bo'sh."""
    url = config.SMARTUP_BASE_URL + NATURAL_PERSON_VIEW_ENDPOINT
    resp = requests.post(url, json={"person_id": str(person_id)},
                         headers=_view_headers(), auth=_auth(), timeout=60)
    resp.raise_for_status()
    data = _unwrap(resp.text)
    if not data:
        return None
    det = data.get("details", {}) or {}
    return {
        "name": data.get("name") or "",
        "tin": "",
        "main_phone": det.get("main_phone") or "",
        "address": det.get("address") or "",
        "vat_code": "",
        "bank_accounts": [],
    }


def fetch_person_details(person_id: str) -> dict | None:
    """Order'dagi `person_id` bo'yicha mijozning to'liq kartasini oladi.
    Qaytaradi (excel_builder kutgan shakl):
        {name, tin, main_phone, address, vat_code,
         bank_accounts: [{bank_name, mfo, bank_account_code, is_main}]}
    Bank ro'yxati view javobida massiv ko'rinishida:
        [bank_name, mfo, account, display, is_main('Y'), currency, ?, state]"""
    if not person_id:
        return None
    url = config.SMARTUP_BASE_URL + PERSON_VIEW_ENDPOINT
    headers = _view_headers()
    resp = requests.post(url, json={"person_id": str(person_id)},
                         headers=headers, auth=_auth(), timeout=60)
    # Mijoz jismoniy shaxs bo'lsa legal_person_view 500 "no_data_found"
    # qaytaradi — u holda jismoniy shaxs kartasidan olamiz.
    if resp.status_code == 500 and "no_data_found" in resp.text:
        return fetch_natural_person_details(person_id)
    resp.raise_for_status()
    data = _unwrap(resp.text)
    if not data:
        return None
    det = data.get("details", {}) or {}
    banks = []
    for b in data.get("bank_accounts", []) or []:
        if not isinstance(b, list) or len(b) < 5:
            continue
        banks.append({
            "bank_name": b[0],
            "mfo": b[1],
            "bank_account_code": b[2],
            "is_main": b[4],
        })
    return {
        "name": data.get("name") or "",
        "tin": det.get("tin") or "",
        "main_phone": det.get("main_phone") or "",
        "address": det.get("address") or "",
        "vat_code": det.get("vat_code") or "",  # view'да odatда yo'q
        "bank_accounts": banks,
    }


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
    """Bitta mijozni `code` (order'dagi person_code) bo'yicha oladi.
    ESLATMA: API `tin` filtrini e'tiborsiz qoldiradi — faqat `code` ishlaydi."""
    if not person_code:
        return None
    url = config.SMARTUP_BASE_URL + LEGAL_PERSON_ENDPOINT
    body = {"code": str(person_code)}
    resp = requests.post(url, json=body, headers=_headers(), auth=_auth(), timeout=60)
    resp.raise_for_status()
    items = resp.json().get("legal_person", []) or []
    return items[0] if items else None


def fetch_all_legal_persons() -> list[dict]:
    """BARCHA yuridik shaxslarni (mijozlarni) bitta so'rovda oladi.
    Har birida: code, tin, vat_code, main_phone, address, bank_accounts (Р/с, МФО).
    Order'da person_code bo'lmasa, tin bo'yicha topish uchun kerak.
    ESLATMA: References limiti 100/kun — main.py'da kuniga 1 marta yangilanadi."""
    url = config.SMARTUP_BASE_URL + LEGAL_PERSON_ENDPOINT
    resp = requests.post(url, json={}, headers=_headers(), auth=_auth(), timeout=120)
    resp.raise_for_status()
    return resp.json().get("legal_person", []) or []


# Oxirgi javobdagi limit holati: {"left": qolgani, "total": sutkalik chek}.
# main.py shu qiymatga qarab tekshirish oralig'ini cho'zadi (limit yarim
# tungacha yetsin). Bo'sh bo'lsa — hali birorta javob olinmagan.
LAST_LIMITS: dict = {}


def _report_limits(limits: dict) -> None:
    """Smartup har javobda kunlik so'rov limitini qaytaradi
    (`limit_quant` — sutkalik chek, `left_limit_quant` — qolgani).

    Limit tugasa so'rovlar rad etiladi va o'sha vaqtda status o'zgargan
    orderlar butunlay o'tkazib yuboriladi — shuning uchun qolgani ozayganda
    logda ogohlantiramiz va qiymatni LAST_LIMITS ga yozamiz.

    DIQQAT: bu limit BUTUN Smartup hisobiga tegishli — shu login bilan
    ishlayotgan boshqa dasturlar ham undan yeydi. Amalda kuzatilgani:
    botning har aylanishiga 1 ta o'z so'rovi + ~1 ta begona so'rov to'g'ri
    keladi, ya'ni 300s interval sutkasiga ~576 ta sarfga olib keladi va
    limit (500) kechqurun tugab qoladi. Shuning uchun main.py intervalni
    qolgan limitga qarab avtomatik cho'zadi."""
    try:
        left = int(limits.get("left_limit_quant"))
        total = int(limits.get("limit_quant"))
    except (TypeError, ValueError):
        return
    LAST_LIMITS["left"] = left
    LAST_LIMITS["total"] = total
    if left <= 0:
        print(f"[LIMIT TUGADI] Smartup kunlik {total} ta so'rov limiti tugadi — "
              f"ertagacha yangi orderlar olinmaydi! POLL_INTERVAL_SECONDS ni "
              f"oshiring.")
    elif left <= max(25, total // 10):
        print(f"[DIQQAT] Smartup kunlik limitidan {left}/{total} ta so'rov qoldi.")


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

    _report_limits(data.get("limits") or {})
    orders = data.get("order", [])

    # Xavfsizlik uchun statusni kod ichida ham tekshiramiz (server filtri yetarli,
    # lekin TARGET_STATUSES bo'sh bo'lsa hammasi o'tadi).
    if config.TARGET_STATUSES:
        orders = [o for o in orders
                  if (o.get("status") or "").strip() in config.TARGET_STATUSES]
    return orders
