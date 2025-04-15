FROM python:3.10-slim

# Çalışma dizini olarak tüm uygulamayı kapsayacak şekilde ayarla
WORKDIR /microbot

# Bağımlılıkları önce kopyala - daha hızlı build için
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Sessions ve veritabanı dizinleri oluştur
RUN mkdir -p sessions
RUN mkdir -p data

# Ortam değişkenleri
ENV PYTHONPATH=/microbot
ENV SESSION_DIR=/microbot/sessions

# Veritabanı tabloları oluştur
RUN python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Port aç
EXPOSE 8000

# Uygulamayı çalıştır
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 