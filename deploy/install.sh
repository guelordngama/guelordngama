#!/usr/bin/env bash
# ============================================================================
#  SafeCity — Installation en une commande sur un VPS (Ubuntu/Debian)
#  Usage (depuis la racine du dépôt cloné) :
#      sudo bash deploy/install.sh
# ============================================================================
set -euo pipefail

# --- Racine du dépôt (le script est dans deploy/) ---
cd "$(cd "$(dirname "$0")/.." && pwd)"

BLUE='\033[1;34m'; GREEN='\033[1;32m'; YELL='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
info() { printf "${BLUE}▶ %s${NC}\n" "$1"; }
ok()   { printf "${GREEN}✓ %s${NC}\n" "$1"; }
warn() { printf "${YELL}! %s${NC}\n" "$1"; }
die()  { printf "${RED}✗ %s${NC}\n" "$1" >&2; exit 1; }

echo
printf "${GREEN}================ SafeCity — Installateur VPS ================${NC}\n\n"

# --- 0. Droits ---
if [ "$(id -u)" -ne 0 ]; then
    die "Lancez le script en root : sudo bash deploy/install.sh"
fi

# --- 1. Dépendances système ---
info "Vérification des dépendances (Docker, git, openssl)…"
if ! command -v docker >/dev/null 2>&1; then
    info "Installation de Docker…"
    apt-get update -qq
    apt-get install -y -qq docker.io docker-compose-plugin
    systemctl enable --now docker
    ok "Docker installé."
else
    ok "Docker déjà présent."
fi
command -v openssl >/dev/null 2>&1 || apt-get install -y -qq openssl
command -v curl >/dev/null 2>&1 || apt-get install -y -qq curl

# Détection de la commande compose (v2 recommandé).
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    apt-get install -y -qq docker-compose-plugin && DC="docker compose"
fi
COMPOSE="$DC --env-file deploy/.env.prod -f docker-compose.prod.yml"

# --- 2. Configuration interactive (deploy/.env.prod) ---
if [ -f deploy/.env.prod ]; then
    warn "deploy/.env.prod existe déjà."
    read -r -p "Le réutiliser (o) ou reconfigurer (n) ? [o/N] " REUSE
    [ "${REUSE:-n}" = "o" ] || rm -f deploy/.env.prod
fi

if [ ! -f deploy/.env.prod ]; then
    info "Configuration interactive…"
    # Domaine DuckDNS préconfiguré pour ce serveur SafeCity.
    DEFAULT_DOMAIN="safecity-rdc.duckdns.org"
    DEFAULT_EMAIL="lucangama20@gmail.com"
    # IP publique du serveur (pour rappel / repli sslip.io).
    IP="$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
    IP="${IP:-169.58.47.76}"
    info "IP détectée : ${IP} — vérifiez que ${DEFAULT_DOMAIN} pointe bien dessus (DuckDNS)."

    read -r -p "Nom de domaine [${DEFAULT_DOMAIN}] : " DOMAIN
    DOMAIN="${DOMAIN:-$DEFAULT_DOMAIN}"
    read -r -p "E-mail (certificats Let's Encrypt) [${DEFAULT_EMAIL}] : " EMAIL
    EMAIL="${EMAIL:-$DEFAULT_EMAIL}"
    read -r -p "Activer les comptes de démonstration au premier démarrage ? [O/n] " DEMO
    if [ "${DEMO:-o}" = "n" ] || [ "${DEMO:-o}" = "N" ]; then SEED="false"; else SEED="true"; fi

    SECRET="$(openssl rand -hex 32)"
    PGPASS="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | cut -c1-24)"

    cat > deploy/.env.prod <<EOF
# Généré par deploy/install.sh le $(date -u +%FT%TZ)
SAFECITY_DOMAIN=${DOMAIN}
CERTBOT_EMAIL=${EMAIL}
SAFECITY_SECRET_KEY=${SECRET}
POSTGRES_PASSWORD=${PGPASS}
SAFECITY_CORS_ORIGINS=https://${DOMAIN}
SAFECITY_SEED_DEMO=${SEED}
BACKUP_INTERVAL_HOURS=24
BACKUP_KEEP=14
EOF
    chmod 600 deploy/.env.prod
    ok "deploy/.env.prod créé (domaine : ${DOMAIN})."
fi

# Recharge les valeurs pour l'affichage final.
# shellcheck disable=SC1091
. ./deploy/.env.prod

# --- 3. Pare-feu (ports 80/443) ---
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    info "Ouverture des ports 80 et 443 (ufw)…"
    ufw allow 80/tcp  >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ok "Ports ouverts."
else
    warn "ufw inactif — vérifiez que les ports 80 et 443 sont ouverts (panneau Contabo)."
fi

# --- 4. HTTPS + démarrage ---
CERT_PATH="/etc/letsencrypt/live/${SAFECITY_DOMAIN}/fullchain.pem"
if $DC -f docker-compose.prod.yml run --rm --entrypoint "test -f ${CERT_PATH}" certbot >/dev/null 2>&1; then
    info "Certificat déjà présent — démarrage de la pile…"
    $COMPOSE up -d --build
else
    info "Émission du certificat HTTPS et démarrage (Let's Encrypt)…"
    sh deploy/init-letsencrypt.sh
fi

# --- 5. Récapitulatif ---
echo
printf "${GREEN}================ Installation terminée ================${NC}\n\n"
ok "App citoyenne  : https://${SAFECITY_DOMAIN}/"
ok "Portail agents : https://${SAFECITY_DOMAIN}/portal/"
ok "API (santé)    : https://${SAFECITY_DOMAIN}/api/health"
echo
if [ "${SAFECITY_SEED_DEMO}" = "true" ]; then
    warn "Comptes de démonstration ACTIFS :"
    echo  "    Opérateur : operateur@safecity.local / safecity123"
    echo  "    Agent     : agent1@safecity.local   / safecity123"
    echo
    echo  "  → Créez un vrai administrateur puis désactivez la démo :"
    echo  "    $COMPOSE exec backend python -m backend.manage create-admin \\"
    echo  "        --email admin@mairie.org --password 'MotDePasseFort' --role admin"
    echo  "    (puis SAFECITY_SEED_DEMO=false dans deploy/.env.prod et : $COMPOSE up -d)"
fi
echo
echo  "Poste opérateur (bureau) : SAFECITY_API=https://${SAFECITY_DOMAIN} python -m desktop.main"
echo  "Logs   : $COMPOSE logs -f backend"
echo  "Statut : $COMPOSE ps"
echo
