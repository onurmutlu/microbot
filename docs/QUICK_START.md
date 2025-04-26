# Hızlı Başlangıç Rehberi

Bu rehber, Telegram MicroBot API projesini hızlıca kurmanıza ve geliştirmeye başlamanıza yardımcı olacaktır.

## Ön Gereksinimler

Projeyi geliştirmek için aşağıdaki yazılımların kurulu olması gerekir:

- Git
- Docker ve Docker Compose
- Python 3.10+ (yerel geliştirme için)
- IDE (VS Code, PyCharm vb.)
- Telegram API anahtarları (API ID, API Hash ve Bot Token)

## 1. Projeyi Klonlama

```bash
# Projeyi klonla
git clone https://github.com/your-organization/microbot.git
cd microbot
```

## 2. Ortam Değişkenlerini Ayarlama

```bash
# Geliştirme için .env dosyasını oluştur
cp .env.dev.example .env.dev
```

`.env.dev` dosyasını açın ve gerekli bilgileri (özellikle Telegram API anahtarlarını) güncelleyin.

## 3. Docker ile Geliştirme Ortamını Başlatma

```bash
# Geliştirme ortamını başlat
docker-compose -f docker-compose.dev.yml up -d

# Log'ları izle
docker-compose -f docker-compose.dev.yml logs -f app
```

## 4. API'ye Erişim

- API: http://localhost:8000
- Swagger Dökümantasyonu: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Adminer (DB Yönetim): http://localhost:8080 (server: db, user: microbot, password: devpassword)

## 5. İlk Kullanıcı Hesabını Oluşturma

```bash
# Kullanıcı oluşturma API'si
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "adminpassword",
    "email": "admin@example.com"
  }'
```

## 6. Telegram API ile Kimlik Doğrulama

1. `/api/auth/login` endpoint'ini kullanarak giriş yapın ve token alın
2. `/api/auth/telegram` endpoint'ini kullanarak Telegram API kimlik bilgilerinizi ayarlayın
3. Doğrulama kodunu alın ve `/api/auth/telegram/verify` endpoint'i ile doğrulayın

## 7. Geliştirme Akışı

### Kod Formatı

Kod yazarken aşağıdaki standartları takip edin:

```bash
# Kodu biçimlendir
docker-compose -f docker-compose.dev.yml exec app black app/

# Import sıralamasını düzenle
docker-compose -f docker-compose.dev.yml exec app isort app/

# Kod kalitesini kontrol et
docker-compose -f docker-compose.dev.yml exec app flake8 app/
```

### Testleri Çalıştırma

```bash
# Tüm testleri çalıştır
docker-compose -f docker-compose.dev.yml exec app pytest

# Belirli bir test dosyasını çalıştır
docker-compose -f docker-compose.dev.yml exec app pytest app/tests/test_scheduled_messaging.py -v

# Kapsam raporu ile çalıştır
docker-compose -f docker-compose.dev.yml exec app pytest --cov=app
```

### Python Debugger İle Hata Ayıklama

VS Code, PyCharm veya diğer IDE'ler ile uzak hata ayıklama yapabilirsiniz. Dockerfile.dev içinde debugpy yüklü ve 5678 portu açık.

**VS Code için `launch.json` örneği:**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: MicroBot Remote",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
          "remoteRoot": "/microbot"
        }
      ]
    }
  ]
}
```

Daha sonra, uygulamayı debugpy ile başlatın:

```bash
docker-compose -f docker-compose.dev.yml exec app python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 8. Veritabanı Migrasyonları

Veritabanı şemasında değişiklik yaptığınızda:

```bash
# Yeni migrasyon oluştur
docker-compose -f docker-compose.dev.yml exec app alembic revision --autogenerate -m "değişiklik açıklaması"

# Migrasyonları uygula
docker-compose -f docker-compose.dev.yml exec app alembic upgrade head
```

## 9. Yeni Bir End-to-End (E2E) Test Senaryosu Ekleme

E2E testleri, sistemin tamamını test eder. Yeni bir senaryo eklemek için:

1. `app/tests/e2e/` dizininde yeni bir test dosyası oluşturun
2. Pytest fixture'larını kullanarak API istemcisi oluşturun
3. API uç noktalarını çağırarak işlevselliği test edin

## 10. Docker Konteynerini Durdurma

```bash
# Geliştirme ortamını durdur
docker-compose -f docker-compose.dev.yml down

# Tüm verileri (veritabanı dahil) silmek isterseniz
docker-compose -f docker-compose.dev.yml down -v
```

## 11. Diğer Yararlı Komutlar

```bash
# Uygulama kabuğunu açma
docker-compose -f docker-compose.dev.yml exec app ipython

# DB Shell'i açma
docker-compose -f docker-compose.dev.yml exec db psql -U microbot -d microbot_dev

# Container içinde komut çalıştırma
docker-compose -f docker-compose.dev.yml exec app python -m app.scripts.your_script
```

## 12. Sorun Giderme

### Docker Build Sorunları
- Docker cache'i temizlemeyi deneyin: `docker-compose -f docker-compose.dev.yml build --no-cache`

### Veritabanı Bağlantı Sorunları
- Veritabanı servisinin çalışıp çalışmadığını kontrol edin: `docker-compose -f docker-compose.dev.yml ps`
- `.env.dev` dosyasında veritabanı bağlantı parametrelerini kontrol edin

### Port Çakışmaları
- Eğer 8000 veya 8080 portları kullanımdaysa, `docker-compose.dev.yml` dosyasındaki port eşlemelerini değiştirin 