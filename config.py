"""
config.py — sozlamalar. MAXFIY ma'lumotlar bu yerda EMAS, `.env` faylda.
Bu fayl xavfsiz (parol yo'q), shuning uchun uni o'zgartirish kerak emas.

Ishlatish:
  1) cp .env.example .env
  2) .env ni ochib haqiqiy qiymatlarni qo'ying
"""

import os
from dotenv import load_dotenv

load_dotenv()  # .env faylni o'qiydi


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _list(key: str, default=None):
    """Vergul bilan ajratilgan qiymatlarni ro'yxatga aylantiradi."""
    raw = os.getenv(key, "")
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return items if items else (default or [])


# ── Smartup API ──
SMARTUP_BASE_URL = _env("SMARTUP_BASE_URL", "https://smartup.online")
SMARTUP_USERNAME = _env("SMARTUP_USERNAME")
SMARTUP_PASSWORD = _env("SMARTUP_PASSWORD")

# ── Telegram ──
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")

# ── Filtrlar ──
TARGET_STATUSES = _list("TARGET_STATUSES", ["to delivered"])
EXCLUDE_WAREHOUSE_CODES = _list("EXCLUDE_WAREHOUSE_CODES")

# ── Tekshirish oralig'i ──
POLL_INTERVAL_SECONDS = int(_env("POLL_INTERVAL_SECONDS", "600"))

# ── 3 ta tashkilot ──
# Maxfiy/o'zgaruvchi qiymatlar .env dan olinadi.
# supplier_* — hujjatda chiqadigan DOIMIY ma'lumot (maxfiy emas), shu yerda.
COMPANIES = [
    {
        "name": "Gynomedix",
        "project_code": _env("GYNOMEDIX_PROJECT_CODE"),
        "filial_id": _env("GYNOMEDIX_FILIAL_ID"),
        "filial_code": _env("GYNOMEDIX_FILIAL_CODE"),
        "producer_codes": _list("GYNOMEDIX_PRODUCER_CODES"),
        "exclude_producer_codes": _list("GYNOMEDIX_EXCLUDE_PRODUCER_CODES"),
        "telegram_chat": _env("GYNOMEDIX_CHAT_ID"),
        "supplier_name": 'MCHJ "GYNOMEDIX"',
        "supplier_address": "Toshkent sh., ... (to'ldiring)",
        "supplier_phone": "",
        "supplier_inn": "",
        "supplier_director": "",
    },
    {
        "name": "BP Pharma",
        "project_code": _env("BP_PHARMA_PROJECT_CODE"),
        "filial_id": _env("BP_PHARMA_FILIAL_ID"),
        "filial_code": _env("BP_PHARMA_FILIAL_CODE"),
        "producer_codes": _list("BP_PHARMA_PRODUCER_CODES"),
        "exclude_producer_codes": _list("BP_PHARMA_EXCLUDE_PRODUCER_CODES"),
        "telegram_chat": _env("BP_PHARMA_CHAT_ID"),
        "supplier_name": 'MCHJ "BP PHARMA"',
        "supplier_address": "... (to'ldiring)",
        "supplier_phone": "",
        "supplier_inn": "",
        "supplier_director": "",
    },
    {
        "name": "Bromedix",
        "project_code": _env("BROMEDIX_PROJECT_CODE"),
        "filial_id": _env("BROMEDIX_FILIAL_ID"),
        "filial_code": _env("BROMEDIX_FILIAL_CODE"),
        "producer_codes": _list("BROMEDIX_PRODUCER_CODES"),
        "exclude_producer_codes": _list("BROMEDIX_EXCLUDE_PRODUCER_CODES"),
        "telegram_chat": _env("BROMEDIX_CHAT_ID"),
        "supplier_name": 'MCHJ "BROMEDIX"',
        "supplier_address": "... (to'ldiring)",
        "supplier_phone": "",
        "supplier_inn": "",
        "supplier_director": "",
    },
]
