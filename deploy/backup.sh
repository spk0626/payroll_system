#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Database backup script — Syntax Asia Salary System
#
# Creates a compressed PostgreSQL dump, keeps 30 days of local backups,
# and optionally copies to remote storage via rclone.
#
# Setup:
#   chmod +x deploy/backup.sh
#   crontab -e
#   # Run at 2:00 AM daily:
#   0 2 * * * /var/www/syntax_asia/deploy/backup.sh >> /var/log/syntax_asia_backup.log 2>&1
#
# Test a restore:
#   gunzip -c /var/backups/syntax_asia/db_YYYYMMDD_HHMMSS.dump.gz \
#     | psql -U syntax_user syntax_asia_db
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
BACKUP_DIR="/var/backups/syntax_asia"
DB_NAME="syntax_asia_db"
DB_USER="syntax_user"
KEEP_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="$BACKUP_DIR/db_$DATE.dump"

# Optional: rclone remote for offsite copies (set to "" to disable)
# Configure rclone first: rclone config
# Example: "backblaze:syntax-asia-backups" or "s3:my-bucket/syntax-asia"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"

# ── Create backup directory ───────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# ── Dump database ─────────────────────────────────────────────────────────────
echo "[$(date)] Starting backup..."
pg_dump \
    --username="$DB_USER" \
    --format=custom \
    --compress=9 \
    "$DB_NAME" \
    > "$DUMP_FILE"

# ── Compress ──────────────────────────────────────────────────────────────────
gzip "$DUMP_FILE"
COMPRESSED="$DUMP_FILE.gz"
SIZE=$(du -sh "$COMPRESSED" | cut -f1)
echo "[$(date)] Backup written: $(basename $COMPRESSED) ($SIZE)"

# ── Rotate old backups ────────────────────────────────────────────────────────
DELETED=$(find "$BACKUP_DIR" -name "*.dump.gz" -mtime +$KEEP_DAYS -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] Rotated $DELETED old backup(s) (older than $KEEP_DAYS days)"
fi

# ── Offsite copy (optional) ───────────────────────────────────────────────────
if [ -n "$RCLONE_REMOTE" ] && command -v rclone &>/dev/null; then
    echo "[$(date)] Copying to remote: $RCLONE_REMOTE"
    rclone copy "$COMPRESSED" "$RCLONE_REMOTE/" \
        --transfers=1 \
        --retries=3 \
        --log-level=WARNING
    echo "[$(date)] Remote copy complete"
else
    echo "[$(date)] Offsite copy skipped (RCLONE_REMOTE not configured)"
fi

echo "[$(date)] Backup complete"