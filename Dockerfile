FROM python:3.10-slim AS builder

WORKDIR /app

# Sadece bağımlılıkları yükle
COPY requirements.prod.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.prod.txt

# Final imaj
FROM python:3.10-slim

# Güvenlik için root olmayan kullanıcı ekle
RUN adduser --disabled-password --gecos '' appuser

WORKDIR /microbot

# Builder aşamasından wheel'leri kopyala
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Uygulama dosyalarını kopyala
COPY . .

# Dizinleri oluştur ve izinleri ayarla
RUN mkdir -p sessions data logs
RUN chown -R appuser:appuser /microbot

# Kullanıcıyı değiştir
USER appuser

# Ortam değişkenleri
ENV PYTHONPATH=/microbot
ENV SESSION_DIR=/microbot/sessions
ENV PYTHONUNBUFFERED=1

# Port aç
EXPOSE 8000

# Healthcheck ekle
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Uygulama başlatma komutu (production)
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--workers", "4", "--log-level", "info", "app.main:app"] 