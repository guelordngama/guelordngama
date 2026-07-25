#!/bin/sh
# ===== SafeCity — Mise à jour d'un déploiement de PRODUCTION existant =====
# Récupère la dernière version, vérifie la configuration (sous-domaine + e-mail),
# reconstruit les conteneurs et contrôle la santé du service.
#
#   sh deploy/update.sh
#
# Pour l'émission/renouvellement du certificat couvrant un NOUVEAU sous-domaine,
# lancez d'abord (une seule fois) : sh deploy/init-letsencrypt.sh
set -e

cd "$(dirname "$0")/.."
ENV=deploy/.env.prod
[ -f "$ENV" ] || { echo "❌ $ENV manquant (copiez deploy/.env.prod.example)."; exit 1; }

CO="docker compose --env-file $ENV -f docker-compose.prod.yml"

echo "▶ 1/4 · Récupération de la dernière version…"
git pull --ff-only || echo "⚠  git pull a échoué — vérifiez la branche déployée."

echo "▶ 2/4 · Vérification de la configuration…"
missing=""
for var in SAFECITY_DOMAIN SAFECITY_PORTAL_DOMAIN SAFECITY_CORS_ORIGINS \
           SAFECITY_SECRET_KEY POSTGRES_PASSWORD; do
    grep -q "^$var=" "$ENV" || missing="$missing $var"
done
if [ -n "$missing" ]; then
    echo "❌ Variables manquantes dans $ENV :$missing"
    echo "   Voir docs/DEPLOIEMENT_CHECKLIST.md (§5 et « Mises à jour »)."
    exit 1
fi
if ! grep -q "^SAFECITY_SMTP_HOST=" "$ENV"; then
    echo "ℹ  SMTP non configuré : sans SMS, les citoyens ne pourront pas recevoir"
    echo "   leur code de vérification. Ajoutez les SAFECITY_SMTP_* (Gmail) au $ENV."
fi

echo "▶ 3/4 · Reconstruction et redémarrage (migrations automatiques)…"
$CO up -d --build

echo "▶ 4/4 · Contrôle de santé…"
sleep 6
# shellcheck disable=SC1090
. "$ENV"
echo "  /api/health :"
curl -sk "https://$SAFECITY_DOMAIN/api/health" || echo "  (pas de réponse — voir: $CO logs backend)"
echo ""
echo "✅ Mise à jour terminée."
echo "   • Citoyens : https://$SAFECITY_DOMAIN"
echo "   • Agents   : https://$SAFECITY_PORTAL_DOMAIN"
echo ""
echo "Astuce : testez l'envoi d'e-mails avec"
echo "  $CO exec backend python -m backend.manage test-email --to vous@example.com"
