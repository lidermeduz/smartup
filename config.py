"""
config.py — sozlamalar. MAXFIY ma'lumotlar bu yerda EMAS, `.env` faylda.
Bu fayl xavfsiz (parol yo'q), shuning uchun uni o'zgartirish kerak emas.

Ishlatish:
  1) cp .env.example .env
  2) .env ni ochib haqiqiy qiymatlarni qo'ying

ARXITEKTURA (haqiqiy Smartup tuzilishiga moslangan):
  - 3 kompaniya BITTA Smartup hisobida (project_code = pfl).
  - Bitta so'rov bilan HAMMA order olinadi (filial_id header BO'SH bo'lishi shart).
  - Kompaniyalar javobdagi `filial_id` + `subfilial_code` bo'yicha KOD ICHIDA
    ajratiladi (Смартап UI'dagi "Проект" ustuni shunga mos keladi):
        Gynomedix : filial_id 18004635
        BP Pharma : filial_id 17986720, subfilial_code 59591
        Bromedix  : filial_id 17986720, subfilial_code 59592
  - Kerakli status: "B#W" (UI'da "В ожидании").
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
SMARTUP_PROJECT_CODE = _env("SMARTUP_PROJECT_CODE", "pfl")  # uchchala kompaniya uchun bitta
SMARTUP_USERNAME = _env("SMARTUP_USERNAME")
SMARTUP_PASSWORD = _env("SMARTUP_PASSWORD")
# Mijoz kartasini (bank ma'lumoti) olish uchun — Smartup web UI'dagi "company_id".
# Bu yordamida org (Gynomedix/BP/Bromedix) doirasidan qat'i nazar mijoz ma'lumoti olinadi.
SMARTUP_COMPANY_ID = _env("SMARTUP_COMPANY_ID", "14160")

# ── Telegram ──
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")

# ── Filtrlar ──
# Faqat shu statusdagi orderlar yuboriladi. Kodlar (Smartup UI):
#   B#N = Новый, B#W = В ожидании, B#S = Отгружен.
TARGET_STATUSES = _list("TARGET_STATUSES", ["B#W"])
# "Терминал" ombor(lar)ining KOD(lar)i — shu ombordagi orderlar umuman
# yuborilmaydi (summasidan qat'i nazar). Har filialning o'z kodi bor:
#   119835 — BP Pharma / Bromedix (filial 17986720) Терминал
#   121374 — Gynomedix (filial 18004635) Терминал
# Standart qiymat SHU YERDA turadi: `.env` da bu satr bo'lmasa ham filtr
# ishlaydi (ilgari .env dan tushib qolganda Терминал guruhga tushib ketgan).
EXCLUDE_WAREHOUSE_CODES = _list("EXCLUDE_WAREHOUSE_CODES", ["119835", "121374"])

# ── Tekshirish oralig'i ──
# DIQQAT: Smartup order eksporti uchun kunlik limit — 500 ta so'rov.
# Sutkada 86400/interval ta so'rov ketadi, shuning uchun interval 180s dan
# kichik bo'lmasligi kerak (120s -> 720 ta so'rov, limitdan oshib ketadi va
# kun oxirida bot orderlarni umuman ko'rmay qoladi).
POLL_INTERVAL_SECONDS = max(180, int(_env("POLL_INTERVAL_SECONDS", "300")))

# ── ИКПУ (МХИК) ──
# Smartup order export ИКПУ qaytarmaydi. Mahsulotlar 2 toifaga bo'linadi:
#   - Aksariyati БАД (sirop, kapsula, tabletka, tomchi) -> IKPU_DEFAULT
#   - Vaginal suppozitoriy / intim krem -> maxsus kod
# Mahsulot NOMIDA (kichik harf) quyidagi kalit so'zlardan biri bo'lsa,
# o'sha maxsus ИКПУ ishlatiladi; aks holda IKPU_DEFAULT.
IKPU_DEFAULT = "02106999028000000"
IKPU_BY_KEYWORD = {
    "03307007005000000": ["супп", "интим", "бактерел", "велора", "регинель"],
}

# ── 3 ta tashkilot ──
# filial_id + subfilial_code — javobni ajratish uchun (header EMAS).
# subfilial_code bo'sh bo'lsa: o'sha filialdagi BARCHA order shu kompaniyaga tegishli.
# supplier_* — hujjatda chiqadigan DOIMIY ma'lumot (maxfiy emas), keyin to'ldiriladi.
COMPANIES = [
    {
        "name": "Gynomedix",
        "filial_id": _env("GYNOMEDIX_FILIAL_ID"),
        "subfilial_code": _env("GYNOMEDIX_SUBFILIAL_CODE"),
        "telegram_chat": _env("GYNOMEDIX_CHAT_ID"),
        "supplier_name": 'MCHJ "GYNOMEDIX"',
        "supplier_address": "Toshkent shaxri Chilonzor tumani. Dumbirobod 4 tor kuchasi 23/2",
        "supplier_phone": "99 830-23-30",
        "supplier_inn": "311818897",
        "supplier_account": "220208000107185255001",
        "supplier_mfo": "01095",
        "supplier_vat_code": "326060260809",
        "supplier_director": "MAMATKULOV S.A.",
    },
    {
        "name": "BP Pharma",
        "filial_id": _env("BP_PHARMA_FILIAL_ID"),
        "subfilial_code": _env("BP_PHARMA_SUBFILIAL_CODE"),
        "telegram_chat": _env("BP_PHARMA_CHAT_ID"),
        # BP Pharma va Bromedix tovarlari PERFECTFOODLAB ishlab chiqaruvchisidan —
        # hujjatdagi Поставщик ham PERFECTFOODLAB.
        "supplier_name": 'MCHJ "PERFECTFOODLAB"',
        "supplier_address": "Toshkent shaxri Chilonzor tumani. Dumbirobod 4 tor kuchasi 23/2",
        "supplier_phone": "71-279-85-55",
        "supplier_inn": "304025510",
        "supplier_account": "20208000300628163001",
        "supplier_mfo": "00433",
        "supplier_vat_code": "326060002559",
        "supplier_director": "KARABAYEV U.A.",
    },
    {
        "name": "Bromedix",
        "filial_id": _env("BROMEDIX_FILIAL_ID"),
        "subfilial_code": _env("BROMEDIX_SUBFILIAL_CODE"),
        "telegram_chat": _env("BROMEDIX_CHAT_ID"),
        "supplier_name": 'MCHJ "PERFECTFOODLAB"',
        "supplier_address": "Toshkent shaxri Chilonzor tumani. Dumbirobod 4 tor kuchasi 23/2",
        "supplier_phone": "71-279-85-55",
        "supplier_inn": "304025510",
        "supplier_account": "20208000300628163001",
        "supplier_mfo": "00433",
        "supplier_vat_code": "326060002559",
        "supplier_director": "KARABAYEV U.A.",
    },
]
