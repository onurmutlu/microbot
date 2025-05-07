# MicroBot

Telegram gruplarını yönetmek için geliştirilmiş bir bot uygulaması.

**Güncel Versiyon: v1.5.0** *(Bakınız: [CHANGELOG.md](CHANGELOG.md))*

## Özellikler

- Telegram grup ve kullanıcı yönetimi
- Gelişmiş otomatik yanıt sistemi (regex desteği ile)
- Zamanlanmış mesaj gönderimi
- Otomatik bot başlatma
- WebSocket tabanlı gerçek zamanlı veri senkronizasyonu
- REST API
- Kullanıcı ve grup hedefleme
- Güvenlik optimizasyonları ve hata düzeltmeleri
- Gelişmiş hata raporlama sistemi
- Otomatik yeniden bağlanma stratejileri
- Performans optimizasyonları

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

## Otomatik Yanıt Sistemi

MicroBot, gelişmiş bir otomatik yanıt sistemi sunar:

- Anahtar kelime eşleştirmesi (virgülle ayrılmış)
- Regex tabanlı eşleştirme (`r:` öneki ile)
- Dinamik değişken desteği (`{name}`, `{username}`, `{group}` vb.)
- Test API'leri ile yanıt kurallarını ve regex ifadelerini test etme

Örnek:
```
# Anahtar kelime eşleştirme
Tetikleyici: merhaba,selam,hi
Yanıt: Merhaba {name}! Nasıl yardımcı olabilirim?

# Regex eşleştirme
Tetikleyici: r:ne zaman (.*?)
Yanıt: {group1} hakkında yakında bilgi vereceğim!
```

## Gerçek Zamanlı Veri Senkronizasyonu

MicroBot, WebSocket tabanlı gerçek zamanlı veri güncellemesi sunar:

- Bağlantı durumu izleme
- Otomatik yeniden bağlanma
- Gerçek zamanlı güncelleme bildirimleri
  - Mesaj şablonu değişiklikleri
  - Otomatik yanıt kuralı güncellemeleri
  - Grup listesi değişiklikleri
  - Zamanlayıcı durumu güncellemeleri

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
