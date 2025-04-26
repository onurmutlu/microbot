# Telegram MicroBot Kurulum Kılavuzu

Bu belge, Telegram MicroBot'u kurma ve yapılandırma sürecini adım adım açıklar.

## 🛠️ Sistem Gereksinimleri

- Docker ve Docker Compose
- 2 GB RAM (minimum)
- 10 GB boş disk alanı
- PostgreSQL 15+
- Redis 7+

## 📋 Kurulum Adımları

### 1. Projeyi Klonlayın

```bash
git clone https://github.com/yourusername/microbot.git
cd microbot
```

### 2. Ortam Değişkenlerini Yapılandırın

`.env.example` dosyasını `.env.prod` olarak kopyalayın ve düzenleyin:

```bash
cp .env.example .env.prod
```

Gerekli alanları doldurun:

- `DATABASE_URL`: PostgreSQL bağlantı URL'si
- `SECRET_KEY`: Güvenli bir rastgele anahtar
- `TELEGRAM_API_ID` ve `TELEGRAM_API_HASH`: Telegram API kimlik bilgileri
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`: Redis yapılandırması

### 3. Docker ile Kurulum

```bash
# Docker imajlarını oluşturun ve çalıştırın
docker-compose -f docker-compose.prod.yml up -d

# Veritabanı tablolarını oluşturun
docker-compose -f docker-compose.prod.yml exec app alembic upgrade head

# Admin kullanıcı oluşturun
docker-compose -f docker-compose.prod.yml exec app python -m scripts.create_admin
```

### 4. SSL Sertifikasını Yapılandırın

```bash
# Let's Encrypt sertifikası almak için
docker-compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d yourdomain.com --email your@email.com --agree-tos

# Nginx'i yeniden başlatın
docker-compose -f docker-compose.prod.yml restart nginx
```

## 🔧 Yedekleme Yapılandırması

Veritabanı yedekleme işlemini yapılandırmak için `.env.prod` dosyasında şu ayarları düzenleyin:

```
BACKUP_RETENTION_DAYS=7
BACKUP_S3_BUCKET=your-bucket-name
BACKUP_S3_ACCESS_KEY=your-access-key
BACKUP_S3_SECRET_KEY=your-secret-key
```

## 📊 İzleme Yapılandırması

Prometheus ve Grafana erişimi için:

- Prometheus: `http://yourdomain.com:9090`
- Grafana: `http://yourdomain.com:3000` (varsayılan giriş: admin/admin)

## 🔄 Güncelleme Prosedürü

Uygulamayı güncellemek için:

```bash
# En son kodu alın
git pull

# Yeni docker imajları oluşturun
docker-compose -f docker-compose.prod.yml build

# Servisleri güncellenmiş imajlarla yeniden başlatın
docker-compose -f docker-compose.prod.yml up -d

# Veritabanı migrasyonlarını uygulayın
docker-compose -f docker-compose.prod.yml exec app alembic upgrade head
```

## ⏮️ Geri Alma Prosedürü

Bir sorun olursa önceki sürüme geri dönmek için:

```bash
# Önceki bir commit'e geri dönün
git checkout [previous-commit-hash]

# Eski imajları yeniden oluşturun
docker-compose -f docker-compose.prod.yml build

# Servisleri yeniden başlatın
docker-compose -f docker-compose.prod.yml up -d

# Veritabanını önceki bir yedekten geri yükleyin (gerekirse)
scripts/restore_backup.sh backups/microbot_20230815_123456.sql.gz
```

## 🔍 Sorun Giderme

### Yaygın Sorunlar ve Çözümleri

1. **Bağlantı Hatası**: Redis veya PostgreSQL'e bağlantı sorunları için container durumlarını kontrol edin:
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

2. **Loglar**: Hata ayıklama için logları inceleyin:
   ```bash
   docker-compose -f docker-compose.prod.yml logs app
   ```

3. **Veritabanı Sorunları**: Veritabanı bağlantısını test edin:
   ```bash
   docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d microbot -c "SELECT 1"
   ```

## 📞 Destek

Sorun yaşarsanız GitHub issue açabilir veya support@example.com adresine e-posta gönderebilirsiniz. 