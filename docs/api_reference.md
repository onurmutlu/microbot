# Telegram MicroBot API Referansı

Bu dokümantasyon, Telegram MicroBot API'sinin endpointlerini ve kullanımını detaylandırır.

## 🔑 Kimlik Doğrulama

Tüm API çağrıları için JWT token tabanlı kimlik doğrulama gereklidir.

### Token Alma

```
POST /api/auth/token
```

**İstek Gövdesi:**
```json
{
  "username": "your_username",
  "password": "your_password"
}
```

**Başarılı Yanıt:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### API Anahtarları

Uzun süreli erişim için API anahtarları kullanabilirsiniz.

```
POST /admin/api-keys
```

**İstek Gövdesi:**
```json
{
  "name": "My API Key",
  "expires_days": 30
}
```

## 📋 Gruplar

### Grupları Listeleme

```
GET /api/groups
```

**Başarılı Yanıt:**
```json
[
  {
    "id": 1,
    "group_id": "1234567890",
    "title": "Grup Adı",
    "username": "grup_kullanici_adi",
    "member_count": 150,
    "is_selected": true,
    "is_active": true,
    "sent_message_count": 42,
    "success_rate": 98.5,
    "last_activity": "2023-08-15T12:30:45"
  }
]
```

### Grup Seçme

```
POST /api/groups/select
```

**İstek Gövdesi:**
```json
{
  "group_ids": ["1234567890", "0987654321"]
}
```

## 📝 Mesaj Şablonları

### Şablonları Listeleme

```
GET /api/message-templates
```

### Şablon Oluşturma

```
POST /api/message-templates
```

**İstek Gövdesi:**
```json
{
  "name": "Şablon Adı",
  "content": "Merhaba, {isim}! Bugün nasılsın?",
  "interval_minutes": 120,
  "cron_expression": "0 */2 * * *",
  "has_structured_content": false
}
```

### Şablon Güncelleme

```
PUT /api/message-templates/{template_id}
```

### Şablon Silme

```
DELETE /api/message-templates/{template_id}
```

## 📨 Mesaj Gönderme

### Manuel Mesaj Gönderme

```
POST /api/messages/send
```

**İstek Gövdesi:**
```json
{
  "template_id": 1,
  "group_ids": ["1234567890", "0987654321"],
  "media_ids": [1, 2]
}
```

## ⏱️ Zamanlayıcı

### Zamanlayıcı Başlatma

```
POST /api/scheduler/start
```

### Zamanlayıcı Durdurma

```
POST /api/scheduler/stop
```

### Zamanlayıcı Durumunu Alma

```
GET /api/scheduler/status
```

**Başarılı Yanıt:**
```json
{
  "running": true,
  "active_templates": 3,
  "messages_last_24h": 42,
  "next_scheduled": "2023-08-15T14:30:00"
}
```

## 📊 Loglar

### Mesaj Loglarını Getirme

```
GET /api/logs
```

**Parametreler:**
- `start_date`: Başlangıç tarihi (YYYY-MM-DD)
- `end_date`: Bitiş tarihi (YYYY-MM-DD)
- `status`: Log durumu (success, error)
- `limit`: Sayfalama limiti
- `offset`: Sayfalama başlangıcı

### Kullanıcı Aktivitelerini Görüntüleme

```
GET /admin/user-activities
```

## 🔒 Güvenlik Notları

1. API anahtarınızı paylaşmayın ve güvenli bir şekilde saklayın.
2. Rate limiting uygulanır. Aşırı istek göndermeyin.
3. Tüm HTTP isteklerinin HTTPS üzerinden yapılması zorunludur.

## ⚠️ Hata Kodları

- `401 Unauthorized`: Kimlik doğrulama hatası
- `403 Forbidden`: Yetkisiz erişim
- `404 Not Found`: Kaynak bulunamadı
- `422 Unprocessable Entity`: Geçersiz giriş verileri
- `429 Too Many Requests`: Rate limit aşıldı
- `500 Internal Server Error`: Sunucu hatası

## 📐 İyi Uygulamalar

1. İsteklerinizi optimize edin ve yalnızca gerekli verileri isteyin.
2. Rate limiting ile karşılaşmamak için isteklerinizi yayın.
3. Telegram API kısıtlamalarına dikkat edin. Bir gruba çok sık mesaj göndermeyin.
4. Gruptaki üyeleri rahatsız edecek içerikler göndermeyin. 