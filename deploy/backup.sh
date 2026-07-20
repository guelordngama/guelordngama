#!/bin/sh
# Sauvegardes automatiques de la base PostgreSQL SafeCity.
# pg_dump compressé à intervalle régulier, avec rotation des anciennes copies.
set -e

INTERVAL_HOURS="${BACKUP_INTERVAL_HOURS:-24}"
KEEP="${BACKUP_KEEP:-14}"
DIR=/backups

mkdir -p "$DIR"
echo "[backup] Démarrage — intervalle ${INTERVAL_HOURS}h, conservation ${KEEP} copies."

while true; do
    STAMP=$(date +%Y%m%d_%H%M%S)
    FILE="$DIR/safecity_${STAMP}.sql.gz"
    if pg_dump | gzip > "$FILE"; then
        echo "[backup] $(date -u +%FT%TZ) sauvegarde créée : $FILE ($(du -h "$FILE" | cut -f1))"
    else
        echo "[backup] ÉCHEC de la sauvegarde à $(date -u +%FT%TZ)" >&2
        rm -f "$FILE"
    fi
    # Rotation : ne garde que les KEEP plus récentes.
    ls -1t "$DIR"/safecity_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
    sleep "$((INTERVAL_HOURS * 3600))"
done
