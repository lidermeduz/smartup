# Smartup → Telegram avtomatik Спецификация yuborish

Deal statusi **"to delivered"** bo'lganda, Smartup'dan ma'lumotni olib,
rasmingizdagi kabi **Спецификация** Excel faylini yasaydi va tegishli
**Telegram guruhga** avtomatik yuboradi. 3 ta tashkilot uchun ishlaydi:
Gynomedix, BP Pharma, Bromedix.

---

## Umumiy tasvir (4 ta qism)

1. **Smartup'dan ma'lumot olish** — `smartup_client.py`
   API'dan "to delivered" statusdagi deal'larni so'raydi.
2. **Excel yasash** — `excel_builder.py`
   Har bir deal'dan Спецификация faylini quradi.
3. **Telegram'ga yuborish** — `telegram_sender.py`
   Faylni botingiz orqali guruhga jo'natadi.
4. **Boshqaruvchi** — `main.py`
   Har 10 daqiqada hammasini takror ishga tushiradi va takror
   yuborishning oldini oladi (`sent_deals.json`).

---

## Boshlashdan oldin yig'ishingiz kerak bo'lgan narsalar

Tajribangiz yo'qligi muammo emas — quyidagilarni topib `config.py` ga
yozib qo'yish kifoya:

- [ ] **Smartup API login va parol** (API foydalanuvchi sifatida)
- [ ] Har 3 tashkilot uchun **project_code** va **filial_id**
- [ ] **Telegram bot tokeni** — @BotFather dan
- [ ] Har 3 guruhning **chat_id** si (botni guruhga qo'shgach olinadi)
- [ ] Smartup'dagi **deal export endpoint** ning aniq manzili —
      siz yuborgan havoladagi so'rov (`#20dc069d...`). Uni
      `smartup_client.py` dagi `ENDPOINT` va `_build_body` ga moslang.

---

## O'rnatish

```bash
# 1) kerakli kutubxonalar
pip install -r requirements.txt

# 2) maxfiy ma'lumotlar uchun .env tayyorlash
cp .env.example .env
# endi .env ni ochib HAQIQIY parol/kodlarni qo'ying

# 3) ishga tushirish
python main.py
```

To'xtatish: `Ctrl + C`.

> Maxfiy ma'lumotlar (parol, token, kodlar) faqat **`.env`** da turadi.
> `config.py` ni o'zgartirish shart emas — u qiymatlarni `.env` dan oladi.
> `.env` faylni hech kimga bermang va git'ga qo'shmang (`.gitignore` da bor).
> Faqat hujjatda chiqadigan doimiy ma'lumotni (supplier manzil/INN/direktor)
> `config.py` dagi COMPANIES ichiga yozasiz.

---

## Telegram bot va chat_id ni qanday olish

1. Telegram'da **@BotFather** ga yozing → `/newbot` → token oling.
2. Botni har 3 guruhga **qo'shing** (yetkazma guruhlariga).
3. chat_id ni olish uchun: botni guruhga qo'shgach, guruhga biror xabar
   yozing, so'ng brauzerda oching:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Javobdan `"chat":{"id":-100...}` qiymatini oling — bu chat_id.

---

## Smartup endpoint'ini moslash (qolgan yagona ish)

Maydon nomlari endi haqiqiy javob sxemangizga moslangan (`order`,
`order_products`, `person_name`, `person_tin`, `product_price`,
`sold_quant`, `vat_percent` ...). Sizdan faqat 3 ta narsa qoldi:

1. **Endpoint YO'LI** — `smartup_client.py` dagi `ENDPOINT`.
   Aniq manzilni siz yuborgan Postman so'rovining tepasidan ko'chiring
   (`.../b/<project>/.../order$export` ko'rinishida).

2. **Status kodi** — `config.py` dagi `TARGET_STATUSES = ["to delivered"]`.
   Bu UI'dagi yorliq. API'dagi ANIQ kod boshqacha bo'lishi mumkin.
   Bitta order javobidagi `"status"` qiymatiga qarab to'g'rilang.

3. **ИКПУ (МХИК)** — javob sxemasida alohida ИКПУ maydoni yo'q.
   `excel_builder.py` da hozir `product_local_code` → `product_code`
   ishlatilyapti. Tizimingizda ИКПУ qaysi maydonda kelishini bitta
   namuna order'da tekshirib, kerak bo'lsa o'sha maydon nomini qo'ying.

> Maslahat: `smartup_client.py` ichidagi `data = resp.json()` dan keyin
> vaqtincha `print(data)` qo'shib, bitta haqiqiy javobni ko'ring —
> status kodi va ИКПУ maydonini ko'z bilan tasdiqlang.

### Sana formati
So'rovda `begin_modified_on` / `end_modified_on` "dd.mm.yyyy" ko'rinishida
yuborilyapti. Agar Smartup boshqa format kutsa (masalan
"yyyy-mm-dd HH:mm:ss"), `main.py` dagi `strftime` qatorini moslang.

---

## Doimiy ishlashi uchun (hosting)

`main.py` doimo ishlab turishi kerak. Variantlar:

- **Eng oddiy:** arzon **VPS** (masalan Ubuntu serveri). U yerda
  `systemd` xizmati yoki `screen`/`tmux` ichida `python main.py` ishlaydi.
- Ofisingizdagi **doimo yoniq kompyuter** ham bo'ladi.
- Bulut (Railway, Render va h.k.) — lekin VPS eng tushunarli.

systemd namunasi (`/etc/systemd/system/smartup-bot.service`):

```ini
[Unit]
Description=Smartup -> Telegram bot
After=network.target

[Service]
WorkingDirectory=/path/to/smartup_telegram
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now smartup-bot
```

---

## Smartup limitlari (yodda tuting)

- Tez-tez ishlatiladigan hujjatlar: **500 so'rov/kun**.
- Faqat oxirgi **7 kunlik** ma'lumotni so'rash mumkin.
- `config.py` dagi `POLL_INTERVAL_SECONDS = 600` (10 daqiqa) xavfsiz:
  3 tashkilot × ~144 = ~432 so'rov/kun.

---

## Fayllar ro'yxati

| Fayl | Vazifasi |
| --- | --- |
| `.env.example` | Maxfiy ma'lumotlar namunasi (nusxalab `.env` qiling) |
| `.env` | HAQIQIY parol/token/kodlar (siz yaratasiz, maxfiy) |
| `config.py` | Sozlamalar — qiymatlarni `.env` dan o'qiydi (parol yo'q) |
| `smartup_client.py` | Smartup API'dan order'larni oladi |
| `excel_builder.py` | Спецификация Excel yasaydi |
| `telegram_sender.py` | Faylni Telegram guruhga yuboradi |
| `main.py` | Hammasini birlashtiruvchi sikl + filtrlar |
| `get_chat_ids.py` | Guruh chat_id larini aniqlash (lokal yordamchi) |
| `requirements.txt` | Kerakli kutubxonalar |
| `.gitignore` | `.env` va vaqtinchalik fayllarni himoyalaydi |
