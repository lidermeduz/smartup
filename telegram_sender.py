"""
telegram_sender.py — tayyor Excel faylni Telegram guruhga yuboradi.
Telegram Bot API'ning sendDocument metodidan foydalanadi.
"""

import os
import requests
import config


def send_excel(chat_id: str, file_path: str, caption: str = "") -> None:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f)}
        data = {"chat_id": chat_id, "caption": caption}
        resp = requests.post(url, data=data, files=files, timeout=120)
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram xatosi: {result}")
