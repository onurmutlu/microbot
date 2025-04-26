# İzleme Rehberi: Metrik ve Logların Yorumlanması

Bu rehber, Telegram MicroBot API'nin izlenmesi, metrik ve logların yorumlanması için kapsamlı bilgiler sunar.

## 1. Log Yapısı ve Formatı

### Log Dosyaları

Sistem aşağıdaki log dosyalarını oluşturur:

- `logs/app.log`: Ana uygulama logları
- `logs/access.log`: HTTP erişim logları
- `logs/error.log`: Hata logları
- `logs/telegram.log`: Telegram API ile ilgili loglar

### Log Formatı

Loglar şu formatta kaydedilir:

```
2023-11-15 13:45:22,123 - app.services.telegram_service - INFO - User 123 connected to Telegram API
```

Format: `tarih - modül_adı - log_seviyesi - mesaj`

## 2. Log Seviyelerini Anlama

- **DEBUG**: Ayrıntılı geliştirme bilgileri, genellikle sorun giderme için
- **INFO**: Normal çalışma durumunu bildiren genel bilgiler
- **WARNING**: Potansiyel sorunlar veya dikkat edilmesi gereken durumlar
- **ERROR**: Uygulamanın bir kısmının çalışmasını engelleyen hatalar
- **CRITICAL**: Tüm uygulamanın çalışmasını durduran ciddi sorunlar

## 3. Önemli Log Mesajları ve Anlamları

### Kritik Loglar ve Anlamları

| Log Mesajı | Anlamı | Önerilen Eylem |
|------------|--------|----------------|
| `Veritabanı bağlantı hatası` | PostgreSQL sunucusuna bağlanılamıyor | DB servisini kontrol et |
| `Unauthorized: Send code first` | Telegram oturumu geçersiz | Kullanıcı yeniden oturum açmalı |
| `FloodWaitError: A wait of X seconds is required` | Telegram API rate limiti | X saniye bekle, API kullanımını azalt |
| `Task exception was never retrieved` | Asyncio görev hatası | Kodda hata ayıkla |
| `SessionRevokedError` | Telegram oturumu iptal edildi | Kullanıcıya yeni oturum aç |

### İzlenmesi Gereken Normal Aktivite Logları

- `Uygulama başlatıldı`: Uygulama başarıyla başladı
- `User X session string kullanılarak bağlanıldı`: Oturum başarılı
- `Scheduler started for user X`: Kullanıcı için zamanlanmış görev başladı
- `Message sent to group X`: Mesaj başarıyla gönderildi

## 4. Prometheus Metrikleri

Prometheus ile şu ana metrikleri izleyebilirsiniz:

### Sistem Metrikleri

- `process_cpu_seconds_total`: CPU kullanım süresi
- `process_resident_memory_bytes`: Bellek kullanımı
- `process_open_fds`: Açık dosya tanımlayıcıları

### Uygulama Metrikleri

- `http_requests_total{endpoint="/api/messages/send"}`: Mesaj gönderme isteği sayısı
- `message_send_duration_seconds`: Mesaj gönderme süresi (saniye)
- `active_schedulers`: Aktif zamanlayıcı sayısı
- `telegram_api_calls_total`: Telegram API çağrı sayısı
- `scheduled_messages_sent_total`: Gönderilen zamanlanmış mesaj sayısı

## 5. Grafana Dashboard'ları

Aşağıdaki dashboard'ları kullanarak sistemi izleyebilirsiniz:

### Sistem Performansı Dashboard'u

- CPU, RAM ve disk kullanımı
- İstek sayısı ve yanıt süreleri
- Aktif oturum sayısı

### Telegram API Dashboard'u

- API çağrı sayıları ve hata oranları
- Rate limit durumu
- Mesaj gönderim başarı/başarısızlık oranları

### Scheduler Dashboard'u

- Aktif zamanlayıcı sayısı
- Zamanlanmış mesaj gönderim sayıları
- Scheduler hata oranları

## 6. Alarmlar ve Eşik Değerleri

Aşağıdaki durumlarda alarm kurulmalıdır:

| Metrik | Eşik Değeri | Öncelik |
|--------|-------------|---------|
| `process_cpu_seconds_total` > 90% | 5 dakika boyunca | Kritik |
| `process_resident_memory_bytes` > 1.5GB | 10 dakika boyunca | Yüksek |
| `http_requests_total` hata oranı > 5% | 15 dakika boyunca | Kritik |
| `telegram_api_errors_total` > 10 | 5 dakika içinde | Yüksek |
| Health check hatası | 3 ardışık kontrol | Kritik |

## 7. İzleme Senaryoları

### Senaryo 1: Yüksek Kaynak Kullanımı

**Belirtiler:**
- CPU kullanımı > 80%
- Bellek kullanımı yükseliyor
- API yanıt süreleri artıyor

**Olası Nedenler:**
- Çok fazla aktif zamanlayıcı
- Veritabanı sorguları optimize edilmemiş
- Bellek sızıntısı

**Çözüm:**
1. En yoğun API endpointlerini kontrol et
2. Aktif kullanıcı ve zamanlayıcı sayısını azalt
3. Docker container'ı yeniden başlat

### Senaryo 2: Telegram API Sorunları

**Belirtiler:**
- `telegram_api_errors_total` artıyor
- Log dosyalarında çok sayıda FloodWaitError

**Olası Nedenler:**
- API rate limitleri aşıldı
- Telegram servisinde sorun var
- API anahtarları geçersiz

**Çözüm:**
1. API çağrı hızını düşür
2. Rate limit parametrelerini güncelle
3. API durumunu kontrol et (https://downdetector.com/status/telegram/)

## 8. Performans Optimizasyonu İpuçları

### Veritabanı Performansı

- Sık kullanılan sorgular için indeksler ekleyin
- N+1 sorgu sorunlarını önleyin
- Büyük veritabanı tabloları için bölümleme düşünün

### API Performansı

- İstek sayısı yüksek endpointler için önbellek ekleyin
- Statik içeriği CDN'e taşıyın
- Rate limiting parametrelerini optimize edin

### Telegram API Kullanımı

- Mesaj gönderimlerini gruplandırın
- Her kullanıcı için dakikada maksimum mesaj sayısını sınırlayın
- API çağrıları arasında uygun bekleme süreleri ekleyin 