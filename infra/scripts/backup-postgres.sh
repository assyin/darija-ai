#!/usr/bin/env bash
# Postgres backup for the Hetzner all-in-one stack.
# Dumps the DB from the running compose container, keeps the last N days,
# and (optionally) uploads to Cloudflare R2 via rclone if configured.
#
# Cron (daily 03:30):
#   30 3 * * * /opt/darija-ai/infra/scripts/backup-postgres.sh >> /var/log/darija-backup.log 2>&1
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-/opt/darija-ai/infra/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-/opt/darija-ai/.env}"
BACKUP_DIR="${BACKUP_DIR:-/opt/darija-ai/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/darija_${STAMP}.sql.gz"

docker compose -f "$COMPOSE_FILE" exec -T postgres \
	pg_dump -U "${POSTGRES_USER:-darija}" "${POSTGRES_DB:-darija_ai}" | gzip > "$OUT"

echo "backup written: $OUT ($(du -h "$OUT" | cut -f1))"

# Rotate local backups.
find "$BACKUP_DIR" -name 'darija_*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete

# Optional offsite copy to R2 (configure an rclone remote named "r2" first).
if command -v rclone >/dev/null 2>&1 && [ -n "${R2_BACKUP_REMOTE:-}" ]; then
	rclone copy "$OUT" "${R2_BACKUP_REMOTE}" && echo "uploaded to ${R2_BACKUP_REMOTE}"
fi
