"""
smartup_client.py — Smartup API bilan gaplashadigan qism.
Haqiqiy deal export sxemasiga moslangan (javob kaliti: "order").

Auth: Basic Auth (login/parol) + sarlavhalar: project_code, filial_id.

QOLGAN YAGONA TODO: endpoint'ning aniq YO'LI (URL path).
Uni siz yuborgan Postman so'rovining tepasidagi manzildan oling
(masalan ".../b/<project>/.../order$export" ko'rinishida) va
pastdagi ENDPOINT ga qo'ying.
"""

import requests
from requests.auth import HTTPBasicAuth
import config


# TODO: aniq yo'lni Postman so'rovidan ko'chiring (project_code o'rni saqlansin)
ENDPOINT = "/b/{project_code}/trade/tdeal/order$export"


def _build_body(company: dict, date_from: str, date_to: str,
                producer_codes=None) -> dict:
    """So'rov tanasi — haqiqiy maydon nomlari bilan."""
    body = {
        "statuses": config.TARGET_STATUSES,     # masalan ["to delivered"]
        "begin_modified_on": date_from,          # "dd.mm.yyyy" formatida
        "end_modified_on": date_to,
    }
    if company.get("filial_code"):
        body["filial_code"] = company["filial_code"]
        body["filial_codes"] = [{"filial_code": company["filial_code"]}]

    # Producer filtri: server tomonda faqat shu ishlab chiqaruvchilar olinadi.
    # producer_codes berilmasa, company["producer_codes"] ishlatiladi.
    pc = producer_codes if producer_codes is not None else company.get("producer_codes")
    if pc:
        body["producer_codes"] = pc
    return body


def fetch_deals(company: dict, date_from: str, date_to: str,
                producer_codes=None) -> list[dict]:
    """Bitta tashkilot bo'yicha kerakli statusdagi order'larni oladi.
    producer_codes berilsa, company'nikidan ustun (exclude logikasi uchun)."""
    url = config.SMARTUP_BASE_URL + ENDPOINT.format(
        project_code=company["project_code"]
    )
    headers = {
        "project_code": company["project_code"],
        "filial_id": str(company["filial_id"]),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    auth = HTTPBasicAuth(config.SMARTUP_USERNAME, config.SMARTUP_PASSWORD)

    resp = requests.post(
        url,
        json=_build_body(company, date_from, date_to, producer_codes),
        headers=headers,
        auth=auth,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    orders = data.get("order", [])   # <-- bosh kalit "order"

    result = []
    for o in orders:
        status = (o.get("status") or "").strip()
        if not config.TARGET_STATUSES or status in config.TARGET_STATUSES:
            result.append(o)
    return result
