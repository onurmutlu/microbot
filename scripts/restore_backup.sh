#!/bin/bash
# Veritabanı Yedek Geri Yükleme Betiği - MicroBot
# Kullanım: ./restore_backup.sh [yedek_dosyası.sql.gz] [--yes]

set -e

# Eğer argüman verilmediyse
if [ $# -lt 1 ]; then
    echo "Kullanım: $0 [yedek_dosyası.sql.gz] [--yes]"
    echo "Örnek: $0 /app/backups/microbot_20230815_123456.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
CONFIRM_FLAG="$2"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/app/backups"
TEMP_DIR="/tmp"
LOG_FILE="${BACKUP_DIR}/restore_log.txt"

# .env dosyasını yükle (eğer mevcut ise)
if [ -f "/app/.env" ]; then
    source /app/.env
fi

# Loglama fonksiyonu
log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1" | tee -a "$LOG_FILE"
}

# Geri yükleme için dizinleri oluştur
mkdir -p "$BACKUP_DIR"
mkdir -p "$TEMP_DIR"

log "Veritabanı geri yükleme başlatılıyor: $BACKUP_FILE"

# Dosyanın varlığını kontrol et
if [ ! -f "$BACKUP_FILE" ]; then
    log "HATA: Belirtilen yedek dosyası bulunamadı: $BACKUP_FILE"
    exit 1
fi

# DATABASE_URL'den parametreleri çıkar
DB_USER=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/([^:]+).*/\1/')
DB_PASS=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^:]+:([^@]+).*/\1/')
DB_HOST=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^@]+@([^:\/]+).*/\1/')
DB_PORT=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^:]+:[^@]+@[^:]+:([0-9]+).*/\1/')
DB_NAME=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^:]+:[^@]+@[^:\/]+:[0-9]+\/([^?]+).*/\1/')

# Kullanıcıya onay sor (eğer --yes bayrağı yoksa)
if [ "$CONFIRM_FLAG" != "--yes" ]; then
    echo "UYARI: Bu işlem mevcut veritabanını tamamen silecek ve yerine '$BACKUP_FILE' dosyasındaki yedeği geri yükleyecektir."
    echo "Veritabanı bilgileri:"
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    
    read -p "Devam etmek istiyor musunuz? (e/h): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ee]$ ]]; then
        log "Geri yükleme iptal edildi"
        exit 0
    fi
fi

# Önce mevcut veritabanının yedeğini al
SAFETY_BACKUP="${BACKUP_DIR}/pre_restore_${DB_NAME}_${TIMESTAMP}.sql.gz"
log "Güvenlik için mevcut veritabanının yedeği alınıyor: $SAFETY_BACKUP"
PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F p | gzip > "$SAFETY_BACKUP"
log "Güvenlik yedeği tamamlandı"

# Yedek dosyasını geçici bir dizine çıkart
TEMP_SQL="${TEMP_DIR}/restore_${TIMESTAMP}.sql"
log "Yedek dosyası açılıyor"
gunzip -c "$BACKUP_FILE" > "$TEMP_SQL"

# Veritabanını geri yükle
log "Veritabanı geri yükleniyor: $DB_NAME"

# Önce mevcut bağlantıları kapat
export PGPASSWORD="$DB_PASS"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "postgres" -c "
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '$DB_NAME'
  AND pid <> pg_backend_pid();"

# Veritabanını kaldır ve yeniden oluştur
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "postgres" -c "DROP DATABASE IF EXISTS $DB_NAME;"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "postgres" -c "CREATE DATABASE $DB_NAME WITH OWNER $DB_USER;"

# Geri yükleme işlemini gerçekleştir
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$TEMP_SQL"

# Geçici dosyayı temizle
rm -f "$TEMP_SQL"

log "Veritabanı geri yükleme işlemi başarıyla tamamlandı."
log "Orijinal yedek dosyası: $BACKUP_FILE"
log "Geri yükleme öncesi güvenlik yedeği: $SAFETY_BACKUP"

echo "Veritabanı geri yükleme işlemi başarıyla tamamlandı."
echo "NOT: Uygulamayı yeniden başlatmanız gerekebilir:"
echo "docker-compose -f docker-compose.prod.yml restart app"

exit 0 