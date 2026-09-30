"""
telegram_sender.py — tayyor Excel faylni Telegram guruhga yuboradi.
Telegram Bot API'ning sendDocument metodidan foydalanadi.
"""

import os
import requests
import config


def send_excel(chat_id: str, file_path: str, caption: str = "") -> dict:
    """Faylni yuboradi va Telegram TASDIQLAGAN manzilni qaytaradi:
        {"message_id": ..., "chat_id": ..., "chat_title": ...}

    Nega javobdagi chat qaytariladi (config'dagi emas): order `sent_deals`
    ga faqat `ok:true` dan keyin yoziladi, ya'ni "yuborildi" belgisi fayl
    QAYERGA tushganini bildirmaydi. `.env` da guruh kodi noto'g'ri bo'lsa,
    hujjat boshqa chatga ketadi-yu yozuv muvaffaqiyatli ko'rinadi va order
    hech qachon qayta yuborilmaydi. Amalda shunday yo'qolganlari:
    "BIG-FAMILY-PHARM" (BP Pharma) va "MEROS PHARM" (Gynomedix).
    Telegram qaytargan chat_id va message_id ni logga yozsak, keyin
    "hujjat qayerga ketdi?" degan savol javobsiz qolmaydi."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f)}
        data = {"chat_id": chat_id, "caption": caption}
        resp = requests.post(url, data=data, files=files, timeout=120)
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram xatosi: {result}")
    msg = result.get("result") or {}
    chat = msg.get("chat") or {}
    return {
        "message_id": msg.get("message_id"),
        "chat_id": chat.get("id"),
        # Shaxsiy chatda title bo'lmaydi — username/ism olinadi.
        "chat_title": (chat.get("title") or chat.get("username")
                       or chat.get("first_name") or ""),
    }
