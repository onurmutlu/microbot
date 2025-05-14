# Admin ve Lisans Yönetimi Konfigürasyonu

Bu doküman MicroBot API'nin admin yönetimi ve lisans sistemi özelliklerinin nasıl yapılandırılacağını ve kullanılacağını açıklar.

## Environment Değişkenleri

Admin ve lisans sistemi için aşağıdaki environment değişkenlerini `.env` dosyasına eklemeniz gerekir:

```
# Admin Settings
ROOT_ADMIN_USERNAME=admin
ROOT_ADMIN_PASSWORD_HASH=$2b$12$tVdyZmXSkfAoiF.JX8rFbeS2lXLkGiEJ/P4keSK4yYrGlnpVYyDCm  # "admin" şifresinin hash'i

# JWT Authentication
SECRET_KEY=super_secret_key_change_in_production
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 saat

# Redis Cache (isteğe bağlı, token karaliste için kullanılır)
CACHE_ENABLED=False
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=
```

## Başlangıç Root Admin

Sistem, `.env` dosyasında tanımlanan bir "root" admin kullanıcısı ile başlar. Bu admin kullanıcısı otomatik olarak süper admin yetkilerine sahiptir ve veritabanında saklanmaz. Güvenlik nedeniyle bu kullanıcının şifresi bcrypt ile hash'lenir.

Default değerler:
- Username: `admin`
- Password: `admin`

Üretime geçmeden önce bu değerleri değiştirmeniz önerilir.

## Şifre Hash'leme

Yeni şifreleri hash'lemek için aşağıdaki Python kodunu kullanabilirsiniz:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password = "your_new_password"
hashed_password = pwd_context.hash(password)
print(hashed_password)
```

## API Endpoint'leri

### Admin Yönetimi
- `POST /api/v1/admin/login` - Admin girişi
- `GET /api/v1/admin/validate` - Admin oturum doğrulama
- `GET /api/v1/admin/me` - Giriş yapan admin bilgilerini getir
- `POST /api/v1/admin/change-password` - Admin şifre değiştirme
- `GET /api/v1/admin/users` - Tüm admin kullanıcıları listele (superadmin yetkisi gerektirir)
- `POST /api/v1/admin/users` - Yeni admin kullanıcı oluştur (superadmin yetkisi gerektirir)
- `PUT /api/v1/admin/users/:id/role` - Admin kullanıcı rolünü değiştir (superadmin yetkisi gerektirir)

### Lisans Yönetimi
- `GET /api/v1/admin/licenses` - Tüm lisansları listele
- `POST /api/v1/admin/licenses` - Yeni lisans oluştur
- `DELETE /api/v1/admin/licenses/:id` - Lisans sil
- `GET /api/v1/licenses/user` - Kullanıcının lisanslarını getir
- `POST /api/v1/licenses/validate` - Lisans anahtarı doğrula
- `POST /api/v1/licenses/assign` - Lisans anahtarını kullanıcıya ata

### Telegram Oturumları
- `GET /api/v1/telegram/sessions` - Kullanıcının Telegram oturumlarını getir
- `POST /api/v1/telegram/start-login` - Telegram girişi başlat (lisans anahtarı kontrol edilir)
- `DELETE /api/v1/telegram/delete-session/:id` - Telegram oturumunu sil
- `POST /api/v1/telegram/set-active-session/:id` - Aktif Telegram oturumunu ayarla
- `GET /api/v1/telegram/user/profile` - Kullanıcı profil bilgilerini getir

## Lisans Sistemi

Lisans sistemi üç farklı lisans tipi destekler:
- `TRIAL` - Ücretsiz deneme sürümü, sınırlı özellikler içerir
- `PRO` - Profesyonel kullanım için tam özellikli lisans
- `VIP` - Gelişmiş özellikler ve öncelikli destek içeren premium lisans

Lisans anahtarları {LICENSE_TYPE}-XXXX-XXXX formatında oluşturulur (örn: PRO-1234-ABCD). Süresi dolan lisanslar otomatik olarak devre dışı bırakılır.

## Token Yönetimi

Admin ve kullanıcı JWT token'ları ayrı yönetilir:

- Admin token'ları 24 saat (veya `.env` dosyasında belirtilen süre) geçerlidir
- Token'lar Redis'te karaliste yöntemi ile kullanılabilir (çıkış yapıldığında)
- JWT payload'ında kullanıcı rolü ve yetkileri saklanır

## Güvenlik Özellikleri

- Bcrypt şifre hash'leme
- JWT token doğrulama
- Rol tabanlı erişim kontrolü
- Rate limiting
- Güvenli CORS yapılandırması

## Admin Rolleri

İki tür admin rolü vardır:
1. `admin`: Temel yönetim işlemleri yapabilir
2. `superadmin`: Tüm yönetim işlemlerini yapabilir, diğer adminleri yönetebilir 