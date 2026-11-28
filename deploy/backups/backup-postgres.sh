
#!/bin/bash

set -Eeuo pipefail

BACKUP_DIR="/opt/backups/myra"
CONTAINER_NAME="myra-postgres"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/myra_${TIMESTAMP}.sql.gz"
TEMP_FILE="${BACKUP_FILE}.tmp"

cleanup() {
    rm -f "$TEMP_FILE"
}
trap cleanup EXIT

echo "Starting Myra PostgreSQL backup: $TIMESTAMP"

docker exec "$CONTAINER_NAME" sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    | gzip > "$TEMP_FILE"

gzip -t "$TEMP_FILE"

mv "$TEMP_FILE" "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"

# Retain local backups for 7 days
find "$BACKUP_DIR" \
    -type f \
    -name "myra_*.sql.gz" \
    -mtime +7 \
    -delete

echo "Backup completed: $BACKUP_FILE"
