#!/bin/bash
# Daily backup script for Email Cleaner database.
# Add to crontab: 0 2 * * * /path/to/deploy/backup.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/email-cleaner}"
DB_PATH="${DB_PATH:-/app/data/email_cleaner.db}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/email_cleaner_${TIMESTAMP}.db"

sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

gzip "$BACKUP_FILE"

find "$BACKUP_DIR" -name "email_cleaner_*.db.gz" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup complete: ${BACKUP_FILE}.gz"
