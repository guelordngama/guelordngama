#!/bin/sh
# ============================================================================
#  SafeCity — Restauration d'une sauvegarde PostgreSQL
#  Usage (sur le VPS, à la racine du dépôt) :
#      sh deploy/restore.sh /chemin/vers/safecity_AAAAMMJJ_HHMMSS.sql.gz
#  ou, pour la dernière sauvegarde du service `backup` :
#      sh deploy/restore.sh --latest
# ============================================================================
set -e

COMPOSE="docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml"

if [ "$1" = "--latest" ]; then
    echo "▶ Recherche de la dernière sauvegarde…"
    LATEST="$($COMPOSE exec -T backup sh -c 'ls -1t /backups/safecity_*.sql.gz 2>/dev/null | head -1')"
    [ -n "$LATEST" ] || { echo "✗ Aucune sauvegarde trouvée dans le volume backups." >&2; exit 1; }
    echo "  Dernière sauvegarde : $LATEST"
    printf "Restaurer cette sauvegarde ? Les données actuelles seront ÉCRASÉES. [o/N] "
    read -r ANS; [ "$ANS" = "o" ] || { echo "Annulé."; exit 0; }
    $COMPOSE exec -T backup sh -c "gunzip -c '$LATEST'" | \
        $COMPOSE exec -T db psql -U safecity -d safecity
elif [ -f "$1" ]; then
    printf "Restaurer « %s » ? Les données actuelles seront ÉCRASÉES. [o/N] " "$1"
    read -r ANS; [ "$ANS" = "o" ] || { echo "Annulé."; exit 0; }
    gunzip -c "$1" | $COMPOSE exec -T db psql -U safecity -d safecity
else
    echo "Usage : sh deploy/restore.sh <fichier.sql.gz>  |  --latest" >&2
    exit 1
fi

echo "✓ Restauration terminée. Vérifiez l'application (https://<domaine>/api/health)."
