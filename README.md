# 🤖 Telegram MicroBot - V1.0a

![Version](https://img.shields.io/badge/version-v1.0a-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Docker-lightgrey)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-Alpha-orange)
![Issues](https://img.shields.io/github/issues/onurmutlu/microbot)
![Stars](https://img.shields.io/github/stars/onurmutlu/microbot)
![Forks](https://img.shields.io/github/forks/onurmutlu/microbot)
![LastCommit](https://img.shields.io/github/last-commit/onurmutlu/microbot)

Bu proje, Telegram üzerinden içerik üreticilerinin (özellikle satış odaklı kullanıcılar) gruplara belirli aralıklarla otomatik olarak tanıtım mesajları göndermesini sağlar.  
Mesajlar, kullanıcının **kendi Telegram hesabı** üzerinden gönderildiği için spam filtrelerine takılmaz.  
Her kullanıcıya özel, izole edilmiş **Docker container microbot** sistemiyle çalışır.

---

## 🚀 Özellikler

✅ Her kullanıcıya ayrı Docker konteyner (tam izolasyon)  
✅ Telegram API üzerinden gerçek kullanıcı mesajı gibi davranır  
✅ Mesaj şablonları, grup listesi ve gönderim sıklığı tanımlanabilir  
✅ Kurulum scripti ile Windows ortamında tek tıkla kurulur  
✅ CLI + MiniApp + API yönetimi destekler  
✅ 2FA (Two-Factor Authentication) desteği vardır  
✅ EC2 üzerinde kolayca dağıtılabilir

---

## 🧠 Mimarisi

```
Kullanıcı
   │
   ▼
MiniApp (Telegram WebApp)
   │  REST API
   ▼
Backend (FastAPI)
   │
   ▼
Docker Container (MicroBot Instance)
   │
   ▼
Telethon (Telegram session)
```

---

## 🔧 Kurulum (Windows için)

### 1. Gereksinimler:
- Python 3.10+  
- Git  
- Docker Desktop  
- PowerShell 5+  

### 2. İlk Kurulum:
```powershell
git clone https://github.com/kullaniciadi/telegram-auto-message-bot.git
cd telegram-auto-message-bot
Set-ExecutionPolicy Bypass -Scope Process
.\setup.ps1
```

Script seni yönlendirecek:
- API ID / HASH / Telefon gir
- Otomatik klasör + container oluştur
- `client_001`, `client_002` vs. şeklinde kullanıcılar eklenir

---

## ⚙️ Docker Yapısı

Her `client_XXX/` klasörü içinde:
- `.env` → API bilgileri
- `docker-compose.yml`
- `run.py` + `requirements.txt` (Telegram gönderim motoru)

Her container izole çalışır. Session'lar `./sessions/` klasörüne kaydedilir.

---

## 📡 API (MiniApp Entegrasyonu İçin)

| Endpoint                 | Metot | Açıklama                             |
|--------------------------|-------|--------------------------------------|
| `/api/start-session`     | POST  | Kullanıcı session başlatır           |
| `/api/list-groups`       | GET   | Kullanıcının grupları listelenir     |
| `/api/add-template`      | POST  | Mesaj şablonu ekler                  |
| `/api/start`             | POST  | Mesaj gönderimini başlatır           |
| `/api/stop`              | POST  | Gönderimi durdurur                   |

---

## 🔐 Güvenlik

- Kullanıcı bilgileri `.env` dosyasında şifrelenmemiştir. Docker host güvenliği sağlanmalıdır.  
- 2FA şifreleri geçici olarak kullanıcıdan alınır, saklanmaz.  
- Session'lar klasörde tutulur (isteğe göre şifrelenebilir).

---

## 📦 Dağıtım

Proje Docker destekli sunuculara kurulabilir:  
- Windows  
- Linux (Ubuntu, Debian)  
- AWS EC2 (tested)  
- VDS/VPS sunucular

---

## 👑 Geliştirme Notları

Yapılacaklar:
- [ ] Admin panel (çoklu bot yönetimi)
- [ ] Jetton (TON) ile ödeme lisans sistemi
- [ ] AI destekli cevaplama (GPT entegrasyonu)
- [ ] DM gelen mesajlara menü & satış akışı

---

## ✨ Katkıda Bulun

PR’lar, öneriler, pull request’ler memnuniyetle karşılanır.  
Yeni microbot örnekleri, geliştirme branch'leri veya MiniApp katkıları için iletişime geçin.

---

## 👤 Proje Sahibi

**Onur Mutlu**  
Telegram: [@OnlyVipsMiniAppBot](https://t.me/OnlyVipsMiniAppBot)  
Repo: [github.com/onurmutlu](https://github.com/onurmutlu)  
Sistem: `MicroBot V1.0a / Telegram Devrimi Başladı`

---

> Bu sadece bir bot değil. Bu, Telegram sokaklarını kodla yeniden yazan bir dijital devrimdir.
