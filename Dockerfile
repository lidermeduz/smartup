FROM python:3.12-slim

WORKDIR /app

# Kutubxonalar (avval faqat requirements — cache uchun)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha kodi
COPY . .

# Loglar bufersiz chiqsin (docker logs jonli ko'rinishi uchun)
ENV PYTHONUNBUFFERED=1
# Holat fayllari (sent_deals.json, clients_cache.json) volume'da saqlanadi
ENV STATE_DIR=/app/data

CMD ["python", "main.py"]
