# Operasyonel Runbook

Bu belge, Telegram MicroBot API'nin operasyonel süreçlerinde karşılaşılan yaygın sorunları ve çözümlerini içerir. Bu runbook, geliştirme, operasyon ve destek ekiplerinin hızlı sorun giderme yapabilmesi için hazırlanmıştır.

## İçindekiler

1. [Sistem Açılışı ve Kapatma](#1-sistem-açılışı-ve-kapatma)
2. [Telegram API Sorunları](#2-telegram-api-sorunları)
3. [Veritabanı Sorunları](#3-veritabanı-sorunları)
4. [Zamanlayıcı Sorunları](#4-zamanlayıcı-sorunları)
5. [API Performans Sorunları](#5-api-performans-sorunları)
6. [Docker ve Container Sorunları](#6-docker-ve-container-sorunları)
7. [Kullanıcı Oturum Sorunları](#7-kullanıcı-oturum-sorunları)
8. [Rutin Bakım İşlemleri](#8-rutin-bakım-işlemleri)

---

## 1. Sistem Açılışı ve Kapatma

### 1.1 Planlı Sistem Başlatma

```bash
# Tüm servisleri başlat
cd /path/to/microbot
docker-compose -f docker-compose.prod.yml up -d

# Sistem durumunu kontrol et
curl http://localhost:8000/health
```

### 1.2 Planlı Sistem Kapatma

```bash
# Zamanlayıcıları durdur
curl -X POST http://localhost:8000/api/scheduler/stop -H "Authorization: Bearer $ADMIN_TOKEN"

# Servisleri durdur
docker-compose -f docker-compose.prod.yml down
```

### 1.3 Acil Sistem Kapatma

```bash
# Tüm servisleri acil durdur (data kaybı olabilir)
docker-compose -f docker-compose.prod.yml down --timeout 10
```

### 1.4 Beklenmeyen Durma Sonrası Yeniden Başlatma

```bash
# Log dosyalarını yedekle
cd /path/to/microbot
mkdir -p ~/logs-backup/$(date +%Y-%m-%d)
cp logs/* ~/logs-backup/$(date +%Y-%m-%d)/

# Servisleri temiz şekilde başlat
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# Durumu kontrol et
docker-compose ps
curl http://localhost:8000/health
```

## 2. Telegram API Sorunları

### 2.1 Telegram Oturum Hatası

**Belirti:** Kullanıcılar "Unauthorized: Send code first" hatası alıyor.

**Çözüm:**
1. Kullanıcının Telegram oturumunu yenileme:
   ```bash
   # Kullanıcı oturum dosyasını sil
   docker exec -it microbot-app sh -c "rm -f sessions/user_123"
   ```
2. Kullanıcıya yeniden oturum açması için bildirim gönder.
3. Kullanıcıya `/api/auth/telegram` endpoint'ini kullanarak yeniden kimlik doğrulaması yapmasını söyle.

### 2.2 Telegram API Rate Limit Hatası

**Belirti:** Loglarda FloodWaitError mesajları, API çağrılarında başarısızlık.

**Çözüm:**
1. Rate limit izleme günlüklerini kontrol et:
   ```bash
   docker-compose logs -f app | grep "FloodWaitError"
   ```
2. Rate limit süresi kadar bekle (genellikle loglarda belirtilir).
3. Scheduler'ı geçici olarak durdur:
   ```bash
   curl -X POST http://localhost:8000/api/scheduler/stop -H "Authorization: Bearer $ADMIN_TOKEN"
   ```
4. Telegram servis ayarlarında gecikme ekle:
   ```python
   # app/config.py - RATE_LIMIT_PER_MINUTE değerini azalt
   RATE_LIMIT_PER_MINUTE: int = 10  # 20'den 10'a düşür
   ```
5. Servisi yeniden başlat:
   ```bash
   docker-compose restart app
   ```

### 2.3 Telethon Bağlantı Sorunu

**Belirti:** Telegram API'ye bağlanırken ConnectionError hatası.

**Çözüm:**
1. Telegram API erişilebilirliğini kontrol et:
   ```bash
   telnet api.telegram.org 443
   ```
2. Sunucu ağ bağlantılarını kontrol et:
   ```bash
   ping api.telegram.org
   curl -I https://api.telegram.org
   ```
3. Docker container DNS ayarlarını kontrol et:
   ```bash
   docker exec microbot-app nslookup api.telegram.org
   ```
4. Gerekirse Docker DNS yapılandırmasını güncelle:
   ```bash
   # /etc/docker/daemon.json
   {
     "dns": ["8.8.8.8", "8.8.4.4"]
   }
   ```
5. Docker servisini yeniden başlat:
   ```bash
   systemctl restart docker
   docker-compose -f docker-compose.prod.yml up -d
   ```

## 3. Veritabanı Sorunları

### 3.1 Veritabanı Bağlantı Hatası

**Belirti:** "Veritabanı bağlantı hatası" logları, API 500 hataları.

**Çözüm:**
1. PostgreSQL servisinin çalıştığını kontrol et:
   ```bash
   docker-compose ps db
   ```
2. Veritabanı loglarını incele:
   ```bash
   docker-compose logs db
   ```
3. Manuel bağlantı testi yap:
   ```bash
   docker exec -it microbot-db psql -U microbot -d microbot -c "SELECT 1"
   ```
4. Bağlantı parametrelerini kontrol et (./env dosyasında):
   ```
   DATABASE_URL=postgresql://microbot:password@db:5432/microbot
   ```
5. Bağlantı havuzu ayarlarını kontrol et (app/database.py):
   ```python
   pool_size=20
   max_overflow=10
   pool_timeout=30
   pool_recycle=1800
   ```

### 3.2 Veritabanı Disk Doluluk Sorunu

**Belirti:** PostgreSQL hizmet dışı, "disk full" hataları.

**Çözüm:**
1. Disk kullanımını kontrol et:
   ```bash
   df -h
   ```
2. PostgreSQL veri dosyalarının boyutunu kontrol et:
   ```bash
   docker exec microbot-db du -sh /var/lib/postgresql/data
   ```
3. Eski logları temizle:
   ```bash
   docker exec microbot-db sh -c "find /var/lib/postgresql/data/pg_log -name '*.log' -mtime +7 -delete"
   ```
4. Gerekirse disk alanı ekle:
   ```bash
   # Bulut sağlayıcınızın konsolunda disk boyutunu artır
   # Ardından dosya sistemini genişlet
   sudo resize2fs /dev/sda1
   ```

### 3.3 PostgreSQL Veritabanı Bakımı

**Belirti:** Veritabanı yavaşlaması, artan sorgu süreleri.

**Çözüm:**
1. Vacuum işlemi çalıştır:
   ```bash
   docker exec -it microbot-db psql -U microbot -d microbot -c "VACUUM ANALYZE;"
   ```
2. İndeksleri yeniden oluştur:
   ```bash
   docker exec -it microbot-db psql -U microbot -d microbot -c "REINDEX DATABASE microbot;"
   ```
3. İstatistikleri güncelle:
   ```bash
   docker exec -it microbot-db psql -U microbot -d microbot -c "ANALYZE;"
   ```

## 4. Zamanlayıcı Sorunları

### 4.1 Zamanlanmış Mesajlar Gönderilmiyor

**Belirti:** Kullanıcılar zamanlanmış mesajların gönderilmediğini bildiriyor.

**Çözüm:**
1. Scheduler durumunu kontrol et:
   ```bash
   curl -X GET http://localhost:8000/api/scheduler/status -H "Authorization: Bearer $USER_TOKEN"
   ```
2. Scheduler loglarını incele:
   ```bash
   docker-compose logs -f app | grep "scheduler"
   ```
3. Aktif şablonları kontrol et:
   ```bash
   curl -X GET http://localhost:8000/api/message-templates?active=true -H "Authorization: Bearer $USER_TOKEN"
   ```
4. Zamanlayıcıyı yeniden başlat:
   ```bash
   curl -X POST http://localhost:8000/api/scheduler/stop -H "Authorization: Bearer $USER_TOKEN"
   curl -X POST http://localhost:8000/api/scheduler/start -H "Authorization: Bearer $USER_TOKEN"
   ```
5. Hala sorun devam ederse, uygulamayı yeniden başlat:
   ```bash
   docker-compose restart app
   ```

### 4.2 Cron İfadesi Hataları

**Belirti:** Cron ifadesi ile zamanlanmış mesajlar beklendiği gibi çalışmıyor.

**Çözüm:**
1. Cron ifadesini doğrula:
   ```bash
   curl -X POST http://localhost:8000/api/scheduler/validate-cron \
     -H "Authorization: Bearer $USER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"cron_expression": "0 9 * * 1"}'
   ```
2. Cron ifadesini görsel olarak kontrol et:
   - https://crontab.guru/ sitesini kullan
3. Cron ifadesini düzelt ve şablonu güncelle:
   ```bash
   curl -X PUT http://localhost:8000/api/message-templates/123 \
     -H "Authorization: Bearer $USER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"cron_expression": "0 9 * * 1"}'
   ```

### 4.3 Zamanlanmış Görevler Bellek Sızıntısı

**Belirti:** Zamanla artan bellek kullanımı, uygulama yavaşlaması.

**Çözüm:**
1. Bellek kullanımını izle:
   ```bash
   docker stats microbot-app
   ```
2. Aktif scheduler sayısını kontrol et:
   ```bash
   curl -X GET http://localhost:8000/api/scheduler/status -H "Authorization: Bearer $ADMIN_TOKEN"
   ```
3. Tüm zamanlayıcıları durdur ve yeniden başlat:
   ```bash
   # Tüm kullanıcıların scheduler'larını durdur
   curl -X POST http://localhost:8000/api/admin/scheduler/stop-all -H "Authorization: Bearer $ADMIN_TOKEN"
   
   # Uygulamayı yeniden başlat
   docker-compose restart app
   
   # Kullanıcılara bildirim gönder (manuel veya uygulama üzerinden)
   ```

## 5. API Performans Sorunları

### 5.1 Yavaş API Yanıt Süreleri

**Belirti:** API yanıt süreleri normalden daha uzun, kullanıcılar gecikme bildiriyor.

**Çözüm:**
1. Yavaş API endpointlerini tanımla:
   ```bash
   docker-compose logs -f app | grep "took longer than"
   ```
2. API kullanım istatistiklerini kontrol et:
   ```bash
   curl -X GET http://localhost:8000/health -H "Authorization: Bearer $ADMIN_TOKEN"
   ```
3. Veritabanı yükünü kontrol et:
   ```bash
   docker exec -it microbot-db psql -U microbot -d microbot -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
   ```
4. Önbellek ekle veya yapılandır:
   ```python
   # app/config.py
   CACHE_EXPIRY_SECONDS = 300  # 5 dakika
   ```
5. Çok fazla eşzamanlı istek varsa, rate limiting'i sıkılaştır:
   ```python
   # app/main.py
   app.add_middleware(
       RateLimitMiddleware,
       calls=30,
       period=60
   )
   ```

### 5.2 Memory Leak Tespiti ve Çözümü

**Belirti:** Zamanla artan bellek kullanımı, düzenli yeniden başlatma gerektiriyor.

**Çözüm:**
1. Bellek kullanımını izle:
   ```bash
   docker stats microbot-app --no-stream
   ```
2. Python bellek profili oluştur:
   ```bash
   # Geçici olarak debug modu etkinleştir
   docker-compose exec app python -m memory_profiler app/main.py
   ```
3. En yaygın bellek sızıntı noktaları:
   - Telegram oturumları için kapanmayan bağlantılar
   - asyncio görevlerinde unutulan referanslar
   - Zamanlayıcılarda biriken görevler
4. Geçici çözüm olarak planlı yeniden başlatma ayarla:
   ```bash
   # Her gece 3'te yeniden başlat
   0 3 * * * cd /path/to/microbot && docker-compose restart app
   ```

## 6. Docker ve Container Sorunları

### 6.1 Docker Container Çökmesi

**Belirti:** API erişilemez, container durumu "Exited"

**Çözüm:**
1. Container durumunu kontrol et:
   ```bash
   docker-compose ps
   ```
2. Çökme nedenini belirle:
   ```bash
   docker-compose logs --tail=100 app
   ```
3. OOM Killer tarafından sonlandırıldıysa:
   ```bash
   dmesg | grep -i 'killed process'
   ```
4. Bellek limitini artır:
   ```yaml
   # docker-compose.yml
   services:
     app:
       deploy:
         resources:
           limits:
             memory: 2G
   ```
5. Container'ı yeniden başlat:
   ```bash
   docker-compose up -d app
   ```

### 6.2 Docker Disk Doluluk Sorunu

**Belirti:** "No space left on device" hataları, container başlatma başarısızlığı.

**Çözüm:**
1. Docker disk kullanımını kontrol et:
   ```bash
   docker system df
   ```
2. Kullanılmayan kaynakları temizle:
   ```bash
   # Kullanılmayan container'ları temizle
   docker container prune -f
   
   # Dangling image'ları temizle
   docker image prune -f
   
   # Kullanılmayan volume'ları temizle
   docker volume prune -f
   ```
3. Eski log dosyalarını sil:
   ```bash
   find /path/to/microbot/logs -name "*.log" -mtime +30 -delete
   ```
4. Tüm Docker sistemini temizle (dikkatli kullan):
   ```bash
   docker system prune -a
   ```

## 7. Kullanıcı Oturum Sorunları

### 7.1 JWT Token Geçerlilik Hataları

**Belirti:** Kullanıcılar "token invalid" veya "token expired" hatası alıyor.

**Çözüm:**
1. JWT yapılandırmasını kontrol et:
   ```python
   # app/config.py
   ACCESS_TOKEN_EXPIRE_MINUTES = 30
   ```
2. Token yenileme sürecini kontrol et:
   ```bash
   # Örnek token yenileme isteği
   curl -X POST http://localhost:8000/api/auth/refresh \
     -H "Content-Type: application/json" \
     -d '{"refresh_token": "eyJhbGciOiJIUzI1..."}'
   ```
3. JWT anahtar rotasyonu yap:
   ```bash
   # Yeni bir SECRET_KEY oluştur
   openssl rand -hex 32
   # Bu anahtarı .env dosyasına ekle
   ```
4. İstemci uygulamalarda token yenileme mantığını güncelle.

### 7.2 Çok Sayıda Başarısız Oturum Açma Girişimi

**Belirti:** Belirli IP adreslerinden çok sayıda başarısız giriş denemesi.

**Çözüm:**
1. Şüpheli IP adreslerini belirle:
   ```bash
   docker-compose logs app | grep "Failed login" | sort | uniq -c | sort -nr
   ```
2. Fail2ban ile şüpheli IP'leri engelle:
   ```bash
   # /etc/fail2ban/jail.local
   [microbot]
   enabled = true
   port = 8000
   filter = microbot
   logpath = /path/to/microbot/logs/access.log
   maxretry = 5
   bantime = 3600
   ```
3. Şüpheli IP'leri manuel olarak engelle:
   ```bash
   ufw deny from 123.45.67.89 to any port 8000
   ```

## 8. Rutin Bakım İşlemleri

### 8.1 Günlük Kontroller

- [ ] Health check endpoint kontrolü
- [ ] Disk kullanım durumu kontrolü
- [ ] Başarısız zamanlanmış mesaj kontrolü
- [ ] Aktif kullanıcı oturum sayısı kontrolü

### 8.2 Haftalık Bakım

- [ ] Veritabanı VACUUM ANALYZE işlemi
- [ ] Docker imajlarını güncelleme
- [ ] Log dosyalarını arşivleme
- [ ] Yedekleme doğrulama testi

### 8.3 Aylık Bakım

- [ ] Güvenlik güncellemelerini uygulama
- [ ] API istatistiklerini analiz etme
- [ ] Veritabanı performans optimizasyonu
- [ ] SSL sertifikalarının geçerlilik kontrolü

### 8.4 Tam Sistem Yedekleme

```bash
#!/bin/bash
# Tam sistem yedekleme betiği

# Tarih formatı
DATE=$(date +%Y-%m-%d)

# Hedef klasör
BACKUP_DIR=/backups/$DATE
mkdir -p $BACKUP_DIR

# Veritabanı yedekleme
docker exec microbot-db pg_dump -U microbot -d microbot > $BACKUP_DIR/db_backup.sql

# Oturum ve yapılandırma dosyalarını yedekleme
cp -r /path/to/microbot/sessions $BACKUP_DIR/sessions
cp -r /path/to/microbot/.env $BACKUP_DIR/env_file

# Log dosyalarını yedekleme
cp -r /path/to/microbot/logs $BACKUP_DIR/logs

# Sıkıştırma
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# Eski yedekleri temizleme (30 günden eski)
find /backups -name "*.tar.gz" -mtime +30 -delete

echo "Yedekleme tamamlandı: $BACKUP_DIR.tar.gz"
```