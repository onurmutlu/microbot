# API Değişiklik Geçmişi

Bu belge, Telegram MicroBot API'nin versiyonlar arasındaki değişikliklerini detaylı olarak belgeler. Her bir değişiklik, API uyumluluğu üzerindeki etkisine göre kategorize edilmiştir.

## Sürüm 1.3.0

**Tarih:** Planlanan

### Eklenen

#### Cron Tabanlı Zamanlanmış Mesajlar
- **Endpoint:** `POST /api/message-templates`
- **Yeni Parametre:** `cron_expression` - Cron formatında zamanlama ifadesi (isteğe bağlı)
- **Açıklama:** Artık mesaj şablonları, sabit aralıklarla gönderilmenin yanı sıra cron ifadesiyle de zamanlanabilir.
- **Örnek İstek:**
  ```json
  {
    "name": "Haftalık Duyuru",
    "content": "Bu haftaki toplantı hatırlatması.",
    "cron_expression": "0 9 * * 1"  // Her Pazartesi saat 9:00
  }
  ```

#### Cron İfadesi Doğrulama 
- **Yeni Endpoint:** `POST /api/scheduler/validate-cron`
- **Parametreler:** `cron_expression` - Doğrulanacak cron ifadesi
- **Dönüş:** Sonraki 5 çalışma zamanı ve geçerlilik durumu

### Değişen

#### Scheduler Durum API'si Genişletildi
- **Endpoint:** `GET /api/scheduler/status` 
- **Eski Dönüş:** Basit durum bilgisi
- **Yeni Dönüş:** Gelişmiş durum bilgisi ve sonraki zamanlanmış mesajlar
  ```json
  {
    "is_running": true,
    "active_templates": 5,
    "messages_sent_24h": 12,
    "next_scheduled_messages": [
      {
        "template_id": 123,
        "template_name": "Pazartesi Duyurusu",
        "next_run": "2023-11-20T09:00:00Z"
      }
    ]
  }
  ```

## Sürüm 1.2.0

**Tarih:** 2023-10-15

### Eklenen

#### Zamanlayıcı Yönetimi API'leri
- **Yeni Endpoint:** `POST /api/scheduler/start`
  - Zamanlanmış mesaj gönderimini başlatır
  - Parametre gerekli değil

- **Yeni Endpoint:** `POST /api/scheduler/stop`
  - Zamanlanmış mesaj gönderimini durdurur
  - Parametre gerekli değil

- **Yeni Endpoint:** `GET /api/scheduler/status`
  - Zamanlayıcı durumunu kontrol eder
  - Dönüş: `{"is_running": true/false, "active_templates": number, "messages_sent_24h": number}`

### Değişen

#### Mesaj Şablonu Oluşturma/Güncelleme
- **Endpoint:** `POST /api/message-templates` ve `PUT /api/message-templates/{template_id}`
- **Yeni Parametre:** `interval_minutes` - Mesajın gönderilme sıklığı (dakika)
- **Varsayılan Değer:** 60 (saatte bir)

## Sürüm 1.1.0

**Tarih:** 2023-09-05

### Eklenen

#### Otomatik Yanıt Sistemi
- **Yeni Endpoint:** `GET /api/auto-replies`
  - Kullanıcının otomatik yanıt kurallarını listeler
  
- **Yeni Endpoint:** `POST /api/auto-replies`
  - Yeni otomatik yanıt kuralı oluşturur
  - **Parametreler:**
    ```json
    {
      "pattern": "merhaba", // veya regex için "r:mer[h]+aba"
      "response": "Merhaba {name}!", // değişken kullanımı
      "is_active": true,
      "priority": 10
    }
    ```
    
- **Yeni Endpoint:** `PUT /api/auto-replies/{rule_id}`
  - Mevcut kuralı günceller
  
- **Yeni Endpoint:** `DELETE /api/auto-replies/{rule_id}`
  - Kuralı siler
  
- **Yeni Endpoint:** `POST /api/auto-replies/test`
  - Otomatik yanıt kurallarını test eder
  - **Parametreler:** `{"message": "Test mesajı"}`
  - **Dönüş:** `{"match": true/false, "response": "Yanıt metni"}`

## Sürüm 1.0.0 (İlk Kararlı Sürüm)

**Tarih:** 2023-08-01

### Temel API Endpointleri

#### Kimlik Doğrulama
- `POST /api/auth/register` - Yeni kullanıcı kaydı
- `POST /api/auth/login` - Kullanıcı girişi ve token alma
- `POST /api/auth/refresh` - Access token yenileme
- `POST /api/auth/telegram` - Telegram API kimlik bilgilerini ayarlama

#### Grup Yönetimi
- `GET /api/groups` - Kullanıcının gruplarını listeler
- `POST /api/groups/discover` - Yeni grupları keşfeder
- `PUT /api/groups/{group_id}` - Grup bilgilerini günceller
- `POST /api/groups/select` - Mesaj gönderilecek grupları seçer

#### Mesaj Yönetimi
- `GET /api/messages` - Gönderilen mesajları listeler
- `POST /api/messages/send` - Mesaj gönderir
- `GET /api/logs` - Mesaj loglarını görüntüler

#### Şablon Yönetimi
- `GET /api/message-templates` - Mesaj şablonlarını listeler
- `GET /api/message-templates/{template_id}` - Belirli bir şablonu görüntüler
- `POST /api/message-templates` - Yeni şablon oluşturur
- `PUT /api/message-templates/{template_id}` - Şablonu günceller
- `DELETE /api/message-templates/{template_id}` - Şablonu siler
- `PATCH /api/message-templates/{template_id}/status` - Şablon durumunu değiştirir

## Geriye Dönük Uyumsuz Değişiklikler

### Sürüm 1.0.0 -> 1.1.0
- Değişiklik yok, tam geriye dönük uyumlu

### Sürüm 1.1.0 -> 1.2.0
- Değişiklik yok, tam geriye dönük uyumlu

### Sürüm 1.2.0 -> 1.3.0
- Zamanlanmış mesaj formatı değişikliği: Cron ifadeleri eklendiğinde eski istemcilerde gösterim sorunları olabilir

## API Kullanım Önerileri

1. **API Versiyonlaması**: Her istek için "Accept" başlığında API versiyonunu belirtin
   ```
   Accept: application/json; version=1.3
   ```

2. **Rate Limiting**: API, dakikada 60 istek ile sınırlandırılmıştır. 429 hata kodları alırsanız istekleri yavaşlatın.

3. **Pagination**: `/api/messages` ve `/api/logs` gibi liste döndüren endpointler için `page` ve `limit` parametrelerini kullanın.

4. **Hata İşleme**: Tüm API hataları aşağıdaki formatta döner:
   ```json
   {
     "detail": "Hata açıklaması"
   }
   ```

5. **Bearer Authentication**: Tüm API isteklerinde (auth endpointleri hariç) Authorization header'ı gereklidir:
   ```
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ``` 