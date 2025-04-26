# Rollback Prosedürleri

Bu belge, Telegram MicroBot API'de sorun durumunda geri alma talimatlarını içerir.

## 1. Docker Deployment Rollback

### Önceki Sürüme Geri Dönme

```bash
# Önceki çalışan sürümü kontrol et
docker images | grep microbot

# Belirli bir imaj sürümüne geri dön
docker-compose stop app
docker-compose -f docker-compose.prod.yml up -d --no-deps app
```

### Git Commit ile Rollback

```bash
# Mevcut sürümü durdur
docker-compose down

# Önceki stabil commit'e geç
git log --oneline
git checkout <commit-hash>

# Yeniden build ve başlat
docker-compose -f docker-compose.prod.yml up -d --build
```

## 2. Veritabanı Rollback

### Alembic ile Veritabanı Migrasyonlarını Geri Alma

```bash
# Mevcut migration sürümünü kontrol et
docker-compose exec app alembic current

# Belirli bir sürüme geri dön
docker-compose exec app alembic downgrade <revision_id>

# Veya bir önceki sürüme geri dön
docker-compose exec app alembic downgrade -1
```

### Veritabanı Yedeklerinden Geri Yükleme

```bash
# PostgreSQL veritabanını yedekten geri yükle
docker-compose down db
docker volume rm microbot_postgres_data
docker-compose up -d db

# Veritabanı başladıktan sonra yedekten geri yükle
cat backup.sql | docker exec -i microbot-db psql -U microbot -d microbot
```

## 3. Telegram Session Rollback

Telegram oturumlarında sorun varsa:

```bash
# Oturum klasörünü yedekle
mv sessions sessions.bad
mkdir sessions

# API'yi yeniden başlat
docker-compose restart app

# Kullanıcı tekrar oturum açmalı
```

## 4. API Değişikliklerini Geri Alma

### Önemli API Değişikliği Rollback Prosedürü

Eğer API'de geriye dönük uyumsuz bir değişiklik yapıldıysa:

1. İstemci uygulamaları eski sürüme güncelle veya istemci uyumluluğunu onar
2. API sunucusunu eski sürüme geri döndür:

```bash
git checkout <last-compatible-version>
docker-compose -f docker-compose.prod.yml up -d --build
```

## 5. Otomatik Rollback Tetikleyicileri

Aşağıdaki durumlarda otomatik rollback başlatılmalıdır:

- Health check endpoint'i 5 dakikadan uzun süre başarısız olursa
- CPU kullanımı %90'ın üzerine çıkarsa
- Bellek kullanımı %85'in üzerine çıkarsa
- API başarı oranı %95'in altına düşerse

### Monitoring Alarmlarını Yapılandırma

```bash
# Prometheus Alert kuralı örneği
cat > prometheus/alerts.yml << EOF
groups:
- name: microbot
  rules:
  - alert: HighCpuUsage
    expr: rate(process_cpu_seconds_total[1m]) * 100 > 90
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Yüksek CPU Kullanımı"
      description: "{{ $labels.instance }} instance'ında CPU kullanımı %90'ın üzerinde."
EOF
```

## 6. İletişim ve Eskalasyon Prosedürü

Rollback süreci sırasında:

1. Slack #prod-alerts kanalında durumu paylaşın
2. Devops ekibini bilgilendirin
3. İşlem 30 dakikadan uzun sürerse CTO'yu bilgilendirin
4. Kullanıcıları etkileyecek bir sorun varsa müşteri destek ekibini bilgilendirin

## 7. Rollback Sonrası İşlemler

Her rollback sonrası şu adımları izleyin:

1. Root cause analizi (RCA) belgesi oluşturun
2. Monitöring göstergelerini kontrol edin
3. Otomatik testleri çalıştırın
4. Örnek manuel testler yapın
5. Rollback ihtiyacını doğuran sorunun düzeltildiğinden emin olun

## 8. Felaket Kurtarma Planı

Tam sistem kaybı durumunda:

1. Yeni bir sunucu temin edin
2. Git reposunu klonlayın
3. En son tam yedekten veritabanını geri yükleyin
4. `.env` dosyasını yapılandırın
5. Docker servisleri başlatın
6. DNS ayarlarını güncelleyin

```bash
# Tam sistem kurtarma script'i
./scripts/disaster_recovery.sh
``` 