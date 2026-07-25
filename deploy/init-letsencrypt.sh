#!/bin/sh
# ===== SafeCity — Émission initiale des certificats HTTPS (Let's Encrypt) =====
# Résout le « problème de l'œuf et la poule » : Nginx a besoin d'un certificat
# pour démarrer, et Certbot a besoin de Nginx pour valider le domaine.
#
# À lancer UNE FOIS après avoir renseigné deploy/.env.prod :
#     sh deploy/init-letsencrypt.sh
set -e

cd "$(dirname "$0")/.."
[ -f deploy/.env.prod ] || { echo "deploy/.env.prod manquant (copiez .env.prod.example)."; exit 1; }
. ./deploy/.env.prod

: "${SAFECITY_DOMAIN:?Definir SAFECITY_DOMAIN dans deploy/.env.prod}"
: "${SAFECITY_PORTAL_DOMAIN:?Definir SAFECITY_PORTAL_DOMAIN dans deploy/.env.prod}"
: "${CERTBOT_EMAIL:?Definir CERTBOT_EMAIL dans deploy/.env.prod}"

COMPOSE="docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml"
LIVE="/etc/letsencrypt/live/$SAFECITY_DOMAIN"

# Le certificat couvre le domaine principal ET le sous-domaine du portail (SAN).
CERT_DOMAINS="-d $SAFECITY_DOMAIN"
[ "$SAFECITY_PORTAL_DOMAIN" != "$SAFECITY_DOMAIN" ] && CERT_DOMAINS="$CERT_DOMAINS -d $SAFECITY_PORTAL_DOMAIN"

echo "1/5 · Certificat temporaire pour démarrer Nginx…"
$COMPOSE run --rm --entrypoint "sh -c \"mkdir -p $LIVE && openssl req -x509 -nodes -newkey rsa:2048 -days 1 -keyout $LIVE/privkey.pem -out $LIVE/fullchain.pem -subj '/CN=$SAFECITY_DOMAIN'\"" certbot

echo "2/5 · Construction et démarrage du backend + Nginx…"
$COMPOSE up -d --build backend nginx db

echo "3/5 · Suppression du certificat temporaire…"
$COMPOSE run --rm --entrypoint "sh -c \"rm -rf /etc/letsencrypt/live/$SAFECITY_DOMAIN /etc/letsencrypt/archive/$SAFECITY_DOMAIN /etc/letsencrypt/renewal/$SAFECITY_DOMAIN.conf\"" certbot

echo "4/5 · Demande du vrai certificat Let's Encrypt (domaine + sous-domaine)…"
$COMPOSE run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
    --email "$CERTBOT_EMAIL" --agree-tos --no-eff-email $CERT_DOMAINS

echo "5/5 · Rechargement de Nginx + démarrage complet…"
$COMPOSE exec nginx nginx -s reload || true
$COMPOSE up -d

echo "✅ HTTPS prêt :"
echo "   • Citoyens : https://$SAFECITY_DOMAIN"
echo "   • Agents   : https://$SAFECITY_PORTAL_DOMAIN  (aussi : https://$SAFECITY_DOMAIN/portal/)"
