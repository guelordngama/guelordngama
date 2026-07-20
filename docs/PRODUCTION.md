# Déploiement en production (VPS Contabo / Ubuntu)

Architecture cible :

```
                         INTERNET (HTTPS / WebSocket)
                                   │
        ┌──────────────┬───────────┴───────────┬──────────────┐
   App citoyenne   Poste opérateur         Portail agents
     (web/)          (desktop/)              (portal/)
        └──────────────┴───────────┬───────────┴──────────────┘
                                   ▼
                        VPS Contabo (Ubuntu)
                    ┌──────────────────────────┐
                    │  Nginx (reverse proxy +  │
                    │       HTTPS / TLS)       │
                    └────────────┬─────────────┘
                     /api  /socket.io  /uploads
                                 ▼
              Backend Flask + Gunicorn/eventlet (WebSocket)
                                 ▼
                            PostgreSQL
             Citoyens · Agents · Alertes · Chat · Historique
                                 ▼
                   Sauvegardes automatiques (pg_dump)
```

## 0. Installation en UNE commande (recommandé)

```bash
ssh root@169.58.47.76
apt update && apt install -y git
git clone <votre-dépôt> safecity && cd safecity
sudo bash deploy/install.sh
```

`deploy/install.sh` installe Docker, génère `deploy/.env.prod` de façon
interactive (domaine sslip.io proposé automatiquement, secrets générés), ouvre
les ports, émet le certificat HTTPS et démarre toute la pile. **Vous pouvez vous
arrêter ici.** La suite décrit les étapes manuelles équivalentes.

---

## 1. Préparer le VPS (manuel)

```bash
ssh root@169.58.47.76
apt update && apt install -y docker.io docker-compose-plugin git
systemctl enable --now docker
git clone <votre-dépôt> safecity && cd safecity
```

Ouvrez les ports **80** et **443** (pare-feu / panneau Contabo).

## 2. Configurer

```bash
cp deploy/.env.prod.example deploy/.env.prod
nano deploy/.env.prod
```
Renseignez au minimum :
- `SAFECITY_DOMAIN` — un nom de domaine. **Sans domaine acheté**, utilisez
  **sslip.io** qui transforme votre IP en nom valide :
  `169.58.47.76` → **`169-58-47-76.sslip.io`**.
- `CERTBOT_EMAIL` — votre e-mail (notifications Let's Encrypt).
- `SAFECITY_SECRET_KEY` — `python3 -c "import secrets; print(secrets.token_hex(32))"`.
- `POSTGRES_PASSWORD` — un mot de passe solide.
- `SAFECITY_CORS_ORIGINS` — `https://<votre-domaine>`.

## 3. Émettre le certificat HTTPS et démarrer

```bash
sh deploy/init-letsencrypt.sh
```
Ce script crée un certificat temporaire, démarre Nginx, obtient le vrai
certificat Let's Encrypt, puis recharge Nginx. Ensuite tout tourne :

- App citoyenne  : `https://<domaine>/`
- Portail agents : `https://<domaine>/portal/`
- API / santé    : `https://<domaine>/api/health`

Le **poste opérateur** (bureau) se connecte au serveur :
```bash
set SAFECITY_API=https://<domaine>      # Windows
python desktop/main.py
```

## 4. Créer un vrai administrateur (et désactiver la démo)

```bash
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml \
  exec backend python -m backend.manage create-admin \
  --email admin@mairie.org --password 'MotDePasseFort' --name 'Admin' --role admin
```
Puis mettez `SAFECITY_SEED_DEMO=false` dans `deploy/.env.prod` et relancez :
```bash
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml up -d
```

## 5. Exploitation

```bash
# Voir l'état / les logs
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml ps
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml logs -f backend

# Mettre à jour le code
git pull && docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml up -d --build
```

### Composants
| Service | Rôle |
|---------|------|
| `nginx` | Reverse proxy, TLS/HTTPS, sert les fronts, proxifie API + WebSocket |
| `backend` | Flask + **Gunicorn/eventlet** (vraies websockets Socket.IO) |
| `db` | PostgreSQL (volume persistant `pgdata`) |
| `certbot` | Renouvellement automatique des certificats (toutes les 12 h) |
| `backup` | `pg_dump` compressé périodique + rotation (volume `backups`) |

## 6. Sauvegardes

Automatiques (service `backup`, par défaut toutes les 24 h, 14 copies gardées).

```bash
# Lister les sauvegardes
docker compose -f docker-compose.prod.yml exec backup ls -lh /backups

# Restaurer une sauvegarde
gunzip -c /chemin/safecity_AAAAMMJJ_HHMMSS.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U safecity safecity
```

## 7. Sécurité (rappel)
Voir [SECURITY.md](SECURITY.md). En production : secret unique, CORS restreint,
compte démo désactivé, HTTPS partout, `X-Forwarded-For` transmis (fait par Nginx
pour la limitation anti force brute).
