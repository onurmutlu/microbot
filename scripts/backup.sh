#!/bin/bash
# Veritabanı Yedekleme Betiği - MicroBot
# Kullanım: ./backup.sh

set -e

# Yapılandırma
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/app/backups"
BACKUP_FILE="microbot_${TIMESTAMP}.sql"
LOG_FILE="${BACKUP_DIR}/backup_log.txt"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}
S3_BUCKET=${BACKUP_S3_BUCKET:-""}
S3_ACCESS_KEY=${BACKUP_S3_ACCESS_KEY:-""}
S3_SECRET_KEY=${BACKUP_S3_SECRET_KEY:-""}

# .env dosyasını yükle (eğer mevcut ise)
if [ -f "/app/.env" ]; then
    source /app/.env
fi

# Loglama fonksiyonu
log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1" | tee -a "$LOG_FILE"
}

# Yedekleme dizini yoksa oluştur
mkdir -p "$BACKUP_DIR"

log "Veritabanı yedeği başlatılıyor..."

# DATABASE_URL'den parametreleri çıkar
DB_USER=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/([^:]+).*/\1/')
DB_PASS=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^:]+:([^@]+).*/\1/')
DB_HOST=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^@]+@([^:\/]+).*/\1/')
DB_PORT=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^:]+:[^@]+@[^:]+:([0-9]+).*/\1/')
DB_NAME=$(echo $DATABASE_URL | sed -r 's/^postgresql:\/\/[^:]+:[^@]+@[^:\/]+:[0-9]+\/([^?]+).*/\1/')

# Veritabanı yedekleme
PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F p > "${BACKUP_DIR}/${BACKUP_FILE}"

# Yedek sıkıştırma
gzip "${BACKUP_DIR}/${BACKUP_FILE}"
COMPRESSED_FILE="${BACKUP_FILE}.gz"

log "Veritabanı yedekleme tamamlandı: ${COMPRESSED_FILE}"

# AWS S3'e yükleme (eğer yapılandırılmışsa)
if [[ -n "$S3_BUCKET" && -n "$S3_ACCESS_KEY" && -n "$S3_SECRET_KEY" ]]; then
    log "AWS S3'e yedek yükleniyor: s3://${S3_BUCKET}/${COMPRESSED_FILE}"
    
    # AWS kimlik bilgilerini ayarla
    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    
    # S3'e kopyala
    aws s3 cp "${BACKUP_DIR}/${COMPRESSED_FILE}" "s3://${S3_BUCKET}/backups/${COMPRESSED_FILE}"
    
    log "S3'e yükleme tamamlandı"
else
    log "S3 yapılandırılmadı, yedek sadece yerel olarak kaydedildi"
fi

# Eski yedekleri temizle
log "Eski yedekler temizleniyor (${RETENTION_DAYS} günden eski)..."
find "$BACKUP_DIR" -type f -name "microbot_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

log "Yedekleme işlemi başarıyla tamamlandı!"
exit 0 