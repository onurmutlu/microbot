# MicroBot

Telegram gruplarını yönetmek için geliştirilmiş bir bot uygulaması.

## Özellikler

- Telegram grup ve kullanıcı yönetimi
- Otomatik yanıt sistemi
- Zamanlanmış mesaj gönderimi
- Otomatik bot başlatma
- WebSocket desteği
- REST API

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. Veritabanını oluşturun:
```bash
alembic upgrade head
```

3. Uygulamayı başlatın:
```bash
python -m app.main
```

## Otomatik Başlatma Özellikleri

MicroBot, uygulama başlatıldığında otomatik olarak aşağıdaki işlemleri yapabilir:

- Aktif kullanıcıların Telegram event handler'larını başlatır
- Zamanlanmış mesaj gönderme sistemlerini başlatır

Bu özellikler user tablosundaki şu alanlara göre etkinleşir:

- `auto_start_bots`: Uygulama başladığında otomatik olarak Telegram event handler'larını başlatır
- `auto_start_scheduling`: Uygulama başladığında otomatik olarak zamanlanmış mesaj gönderme sistemini başlatır

Kullanıcılar bu ayarları API üzerinden yönetebilir:

```bash
# Ayarları görüntülemek için
GET /api/scheduler/auto-start-settings

# Ayarları güncellemek için
POST /api/scheduler/auto-start-settings
```

## Sistem Yönetimi

Sistem durumunu kontrol etmek ve handler'ları yeniden başlatmak için:

```bash
# Sistem durumunu kontrol etmek için
GET /system/status

# Tüm handler'ları yeniden başlatmak için
POST /system/restart-handlers
```

## API Dokümantasyonu

API dokümantasyonuna erişmek için:
```
http://localhost:8000/docs
```

## WebSocket Bağlantısı

WebSocket bağlantısı için:
```
ws://localhost:8000/ws/{client_id}
```

## Test

Testleri çalıştırmak için:
```bash
pytest
```

## Docker ile Çalıştırma

Uygulamayı Docker ile çalıştırmak için:

```bash
# Geliştirme ortamı
docker-compose -f docker-compose.dev.yml up -d

# Üretim ortamı
docker-compose -f docker-compose.prod.yml up -d
```

## Lisans

MIT
