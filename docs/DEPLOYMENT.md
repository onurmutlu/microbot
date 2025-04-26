# Telegram MicroBot API Deployment Kılavuzu

Bu kılavuz, Telegram MicroBot API'yi üretim ortamında dağıtmak için adım adım talimatlar sağlar.

## Önkoşullar

- Docker ve Docker Compose kurulumu
- PostgreSQL 14+ veritabanı erişimi
- Telegram API anahtarları (API ID, API Hash, Bot Token)
- DNS yapılandırması (opsiyonel, domain kullanılacaksa)

## 1. Kaynak Kodunu Edinme

```bash
# Projeyi klonla
git clone https://github.com/your-organization/microbot.git
cd microbot
```

## 2. Ortam Değişkenleri

`.env` dosyasını oluşturun:

```bash
# .env dosyası oluştur
cp .env.example .env
```

Aşağıdaki değerleri düzenleyin:

```ini
# Telegram API anahtarları
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
USER_MODE=true
PHONE=+901234567890

# PostgreSQL ayarları
POSTGRES_USER=microbot
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=microbot
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://microbot:your_secure_password@db:5432/microbot

# Güvenlik
SECRET_KEY=your_random_secret_key_at_least_32_characters
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Uygulama Ayarları
APP_ENV=production
DEBUG=False
LOG_LEVEL=INFO
FRONTEND_URL=http://your-frontend-domain.com
```

## 3. Docker Compose ile Deployment

### Temel Deployment (Tek Sunucu)

```bash
# Docker imajını oluştur ve çalıştır
docker-compose up -d

# Log kontrol
docker-compose logs -f
```

### Ölçeklenebilir Deployment (Çoklu Sunucu)

Çok sunuculu bir ortam için, docker-compose.prod.yml dosyasını düzenleyin:

```bash
# Üretim ortamında çalıştır
docker-compose -f docker-compose.prod.yml up -d
```

## 4. Veritabanı Migrasyonları

```bash
# Container içinde migrasyon yap
docker-compose exec app alembic upgrade head
```

## 5. TLS/SSL Yapılandırması (HTTPS)

Nginx için SSL yapılandırması:

```bash
# Nginx yapılandırma dosyası oluştur
cat > nginx/microbot.conf << EOF
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    location / {
        proxy_pass http://app:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
```

Certbot ile SSL sertifikası alma:

```bash
# Certbot ile SSL sertifikası alma
certbot certonly --webroot -w /var/www/html -d your-domain.com
```

## 6. Health Check

Uygulamanın çalışıp çalışmadığını kontrol edin:

```bash
curl http://localhost:8000/health
```

## 7. Güvenlik Duvarı Yapılandırması

UFW ile temel güvenlik duvarı ayarları:

```bash
# SSH, HTTP ve HTTPS portlarına izin ver
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp

# Diğer tüm portları kapat
ufw enable
```

## 8. Günlük Bakım İşlemleri

Log rotasyonu için logrotate yapılandırması:

```bash
# /etc/logrotate.d/microbot dosyası oluştur
cat > /etc/logrotate.d/microbot << EOF
/path/to/microbot/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data www-data
}
EOF
```

## 9. Sistem Monitöring Ayarları

Prometheus ve Grafana ekleme (opsiyonel):

```bash
# Docker Compose dosyasına monitoring servisleri ekle
cat >> docker-compose.prod.yml << EOF
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped
    
  grafana:
    image: grafana/grafana
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    restart: unless-stopped
    
volumes:
  prometheus_data:
  grafana_data:
EOF
```

## 10. Uygulama Güncelleme

```bash
# En son değişiklikleri çek
git pull origin main

# Docker imajını yeniden oluştur ve başlat
docker-compose -f docker-compose.prod.yml up -d --build
```

## Sorun Giderme

- **502 Bad Gateway**: Nginx proxy ayarlarını kontrol edin
- **Veritabanı Bağlantı Hatası**: PostgreSQL servisinin çalıştığından emin olun
- **Telegram API Hatası**: API anahtarlarınızı kontrol edin 