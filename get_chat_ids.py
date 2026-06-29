"""
get_chat_ids.py — Telegram guruh(lar) chat_id sini aniqlash uchun.

ISHLATISH:
  1) @BotFather dan bot token oling.
  2) Botni KERAKLI GURUHLARGA qo'shing (a'zo yoki admin).
  3) HAR BIR guruhga biror xabar yozing (masalan "test").
     (Bot faqat o'zi qo'shilgandan KEYINGI xabarlarni ko'radi.)
  4) Tokenni bering — ikki yo'l:
        - shu papkadagi .env faylga TELEGRAM_BOT_TOKEN=... deb yozing, YOKI
        - pastdagi TOKEN o'zgaruvchisiga to'g'ridan-to'g'ri qo'ying.
  5) Ishga tushiring:  python get_chat_ids.py
  6) Chiqqan id larni config/.env ga ko'chiring.

Eslatma: guruh id lari manfiy bo'ladi (masalan -1001234567890).
Bu skript qo'shimcha kutubxona talab qilmaydi.
"""

import os
import sys
import urllib.request
import json

# ── Yo'l 2: tokenni to'g'ridan-to'g'ri shu yerga qo'yishingiz mumkin ──
TOKEN = "BU_YERGA_BOT_TOKEN"


def _read_token_from_env_file() -> str:
    """Shu papkadagi .env dan TELEGRAM_BOT_TOKEN ni oladi (bo'lsa)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip()
    return ""


def get_token() -> str:
    return (os.getenv("TELEGRAM_BOT_TOKEN")
            or _read_token_from_env_file()
            or (TOKEN if TOKEN != "BU_YERGA_BOT_TOKEN" else ""))


def main():
    token = get_token()
    if not token:
        print("Token topilmadi. .env ga TELEGRAM_BOT_TOKEN qo'ying yoki "
              "skript ichidagi TOKEN ni to'ldiring.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
    except Exception as e:
        print("So'rovda xato:", e)
        sys.exit(1)

    if not data.get("ok"):
        print("Telegram xatosi:", data)
        sys.exit(1)

    updates = data.get("result", [])
    if not updates:
        print("Hech qanday yangilanish yo'q.")
        print("-> Botni guruhga qo'shdingizmi? Guruhga xabar yozdingizmi?")
        print("-> Bot @BotFather da 'Group Privacy' OFF bo'lishi kerak,")
        print("   yoki botni guruhda ADMIN qiling.")
        return

    seen = {}
    for upd in updates:
        msg = (upd.get("message") or upd.get("channel_post")
               or upd.get("my_chat_member") or {})
        chat = msg.get("chat")
        if not chat:
            continue
        cid = chat.get("id")
        if cid in seen:
            continue
        seen[cid] = {
            "id": cid,
            "type": chat.get("type"),
            "title": chat.get("title") or chat.get("username")
                     or chat.get("first_name", ""),
        }

    if not seen:
        print("Chat topilmadi. Guruhga xabar yozib, qayta urinib ko'ring.")
        return

    print("\n=== Topilgan chatlar ===")
    for c in seen.values():
        print(f'  title : {c["title"]}')
        print(f'  type  : {c["type"]}')
        print(f'  id    : {c["id"]}')
        print("  " + "-" * 30)
    print("\nGuruh id larini config.py dagi telegram_chat ga ko'chiring.")


if __name__ == "__main__":
    main()
