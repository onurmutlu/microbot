# Değişiklik Günlüğü

Bu proje, [Semantik Sürümleme](https://semver.org/lang/tr/) kurallarını takip etmektedir.

## [1.4.0] - 2024-04-27

### Gelişmiş Otomatik Yanıt Sistemi
- Regex destek motoru iyileştirildi
- Değişken işleme mekanizması geliştirildi
- Yanıt kuralları test arayüzü güncellendi
- Regex test aracı optimize edildi

### Şablon Yönetimi Geliştirmeleri
- Şablon yönetim arayüzü yenilendi
- Varsayılan şablonlar eklendi
- Şablon kategorileri eklendi
- Şablonlar arası kopyalama özelliği

### WebSocket Entegrasyonu
- Gerçek zamanlı veri güncelleme mekanizması iyileştirildi
- WebSocket güvenlik kontrolleri güçlendirildi
- Bağlantı yönetimi geliştirmeleri
- Veri senkronizasyon optimizasyonları

### Performans İyileştirmeleri
- Veritabanı sorguları optimize edildi
- Telegram API bağlantı yönetimi iyileştirildi
- Bellek kullanımı azaltıldı
- Yanıt süreleri iyileştirildi

### Hata Düzeltmeleri
- WebSocket bağlantı kopması sorunları giderildi
- Otomatik yanıt kurallarındaki eşleştirme hataları düzeltildi
- Zamanlayıcı servisindeki bellek sızıntısı sorunu çözüldü
- API erişim kontrollerindeki güvenlik açıkları kapatıldı

## [1.3.0] - 2024-03-21

### Frontend Geliştirmeleri
- WebSocket bağlantı yönetimi tamamlandı
- Gerçek zamanlı veri senkronizasyonu implementasyonu
- Otomatik yeniden bağlanma mekanizması eklendi
- UI/UX iyileştirmeleri yapıldı
- Hata yönetimi ve kullanıcı bildirimleri geliştirildi
- Performans optimizasyonları yapıldı

### Backend Geliştirmeleri
- WebSocket servisi güçlendirildi
- Redis entegrasyonu ve pub/sub desteği eklendi
- Rate limiting ve güvenlik kontrolleri geliştirildi
- İzleme ve loglama sistemi güncellendi
- Hata yönetimi iyileştirildi
- Performans optimizasyonları yapıldı

### Güvenlik İyileştirmeleri
- JWT token doğrulama sistemi güçlendirildi
- XSS ve enjeksiyon koruması eklendi
- Rate limiting kuralları güncellendi
- Bağlantı güvenliği artırıldı

### Yeni Özellikler
- Gerçek zamanlı mesaj şablonu güncelleme
- Otomatik yanıt kuralları yönetimi
- Grup yönetimi ve senkronizasyonu
- Zamanlayıcı durumu takibi
- Bağlantı sağlığı izleme

### Düzeltmeler
- WebSocket bağlantı sorunları giderildi
- Veri senkronizasyon hataları düzeltildi
- Performans sorunları optimize edildi
- Güvenlik açıkları kapatıldı

### Teknik İyileştirmeler
- Kod kalitesi artırıldı
- Test coverage genişletildi
- Dokümantasyon güncellendi
- Deployment süreçleri iyileştirildi

## [1.2.0] - 2024-03-25

### Frontend Geliştirmeleri
- WebSocket istemci implementasyonu tamamlandı
- Gerçek zamanlı veri senkronizasyonu eklendi
- Otomatik yeniden bağlanma mekanizması eklendi
- Hata yönetimi geliştirildi
- UI/UX iyileştirmeleri yapıldı

### Backend Geliştirmeleri
- WebSocket sunucusu optimizasyonu
- Veri senkronizasyonu iyileştirmeleri
- Performans optimizasyonları
- Hata yönetimi geliştirmeleri

## [1.1.0] - 2024-03-22

### Frontend-Backend Entegrasyonu
- WebSocket bağlantı yönetimi eklendi
- Veri senkronizasyonu mekanizması kuruldu
- Otomatik yeniden bağlanma eklendi
- Hata yönetimi geliştirildi

### Backend Geliştirmeleri
- WebSocket sunucusu implementasyonu
- Gerçek zamanlı olay yönetimi
- Kullanıcı kimlik doğrulama
- Veri senkronizasyonu

## [1.0.0] - 2024-03-20

### Eklenen
- WebSocket tabanlı gerçek zamanlı mesajlaşma
- Redis pub/sub mesajlaşma altyapısı
- Çevrimdışı mesaj kuyruğu (7 gün saklama)
- Kullanıcı durumu takibi (çevrimiçi/çevrimdışı)
- Otomatik bağlantı yönetimi
- Detaylı hata loglama
- Miniapp entegrasyonu için standart mesaj formatı
- WebSocket protokol standardizasyonu

### Değişen
- Mesajlaşma altyapısı WebSocket'e geçirildi
- Redis entegrasyonu eklendi
- Bağlantı yönetimi iyileştirildi
- Hata yönetimi geliştirildi

### Düzeltilen
- WebSocket bağlantı kopması sorunları
- Mesaj kaybı sorunları
- Performans optimizasyonları

## [0.9.0] - 2024-03-15

### Eklenen
- İlk WebSocket implementasyonu
- Temel Redis entegrasyonu
- Basit mesajlaşma özellikleri

### Düzeltilen
- Bağlantı yönetimi sorunları
- Mesaj formatı standardizasyonu

## [0.7.0] - 2024-02-15

### Eklenenler
- WebSocket tabanlı gerçek zamanlı veri senkronizasyonu
- Bağlantı durumu göstergesi
- Otomatik yeniden bağlanma mekanizması
- Global hata yönetimi (Error Boundary)
- Zustand tabanlı state management
- Performans optimizasyonları

### Değişiklikler
- WebSocket entegrasyonu ile gerçek zamanlı veri güncellemeleri
- Bağlantı durumu izleme ve kullanıcı bildirimleri
- Hata yönetimi merkezileştirildi
- State management çözümü eklendi

## [0.6.0] - 2024-02-01

### Eklenenler
- WebSocket tabanlı gerçek zamanlı veri senkronizasyonu
- Bağlantı durumu göstergesi
- Otomatik yeniden bağlanma mekanizması
- Gerçek zamanlı güncelleme bildirimleri
  - Mesaj şablonu değişiklikleri
  - Otomatik yanıt kuralı güncellemeleri
  - Grup listesi değişiklikleri
  - Zamanlayıcı durumu güncellemeleri

### Değişiklikler
- API iletişimi WebSocket desteği ile genişletildi
- Kullanıcı arayüzüne bağlantı durumu göstergesi eklendi
- Veri güncellemeleri için polling yerine WebSocket kullanılmaya başlandı

## [0.2.0] - 2023-09-10

### Eklenen
- Gelişmiş otomatik yanıt sistemi
  - Regex tabanlı yanıt desenleri desteği (`r:` öneki ile)
  - Yanıtlarda değişken kullanımı (`{değişken}` formatı)
  - Test endpoint'leri ve regex test aracı
- Yanıt sistemine yeni API endpoint'leri
  - GET `/api/auto-replies` - Yanıt kurallarını listeleme
  - POST `/api/auto-replies/test` - Yanıt kurallarını test etme
  - POST `/api/auto-replies/test-regex` - Regex ifadelerini test etme
- Kapsamlı birim testleri

### Değiştirilen
- TelegramService sınıfı, gelişmiş yanıt algoritması kullanacak şekilde güncellendi
- API dökümantasyonu iyileştirildi
- Router işlevleri optimize edildi

### Düzeltilen
- Regex eşleşmelerinde oluşan hatalar giderildi
- TelegramService'deki bellek sızıntıları önlendi
- Token yenileme sürecindeki hatalar giderildi

## [0.1.0] - 2023-08-15

### Eklenen
- Temel veritabanı modelleri (User, Group, MessageTemplate, MessageLog, TargetUser, AutoReplyRule)
- Kullanıcı kimlik doğrulama ve JWT token sistemi
- Telegram API ile bağlantı kurma altyapısı
- Grup listeleme ve yönetim özellikleri
- Temel mesaj şablonu oluşturma ve düzenleme
- Manuel mesaj gönderimi için API endpoint'leri

### Değiştirilen
- SQLite veritabanı yapılandırması optimize edildi
- Telethon bağlantı yönetimi iyileştirildi

### Düzeltilen
- API yanıt formatları standardize edildi
- Oturum yönetimi güvenlik açıkları giderildi

## [0.0.1] - 2023-07-20

### Eklenen
- Proje başlangıç yapısı
- FastAPI ve SQLAlchemy entegrasyonu
- Temel proje dosyaları ve klasör yapısı 