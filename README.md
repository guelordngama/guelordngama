# 🛡️ SafeCity — Plateforme d'alerte citoyenne

**Version 1.2.0** · voir le [journal des modifications](CHANGELOG.md).

Application professionnelle de sécurité urbaine : un citoyen signale un danger
en un geste depuis son téléphone, et le centre de surveillance de la mairie
reçoit, localise et traite l'alerte **en temps réel**.

```
📱 App citoyenne (Web)  ──►  🌐 Backend Flask modulaire  ──►  🖥️ Poste opérateur (PySide6)
   Alerte + GPS + IA          factory · blueprints · services     Tableau de bord · Carte · Actions
```

## ✨ Fonctionnalités

**Application citoyenne** (`web/`) — **compte citoyen** (inscription /
connexion, numéro de téléphone unique vérifié), bouton d'alerte, GPS
automatique, type de danger (vol, braquage, incendie, accident, violence,
autre), photo, message vocal, distance/ETA, confirmation avec carte
OpenStreetMap.

**Backend** (`backend/`) — API REST + temps réel Socket.IO, **classification IA**
des incidents (scikit-learn), calcul de distance (Haversine) et d'ETA,
authentification bcrypt + JWT, base **PostgreSQL** (SQLite en repli local / tests).

**Poste opérateur** (`desktop/`) — **tableau de bord** (en-tête d'accueil,
pastille de situation, tuiles cliquables), alertes en direct avec marquage
**non lu**, carte interactive (Qt WebEngine + Leaflet), graphiques (Qt Charts),
sons de notification, actions **Voir sur la carte / Affecter une équipe /
Clôturer**.

**Portail agents** (`portal/`) — vue web temps réel pour les agents de terrain :
alertes, carte, prise en charge, messagerie et sons de notification.

**Messagerie** (poste opérateur ↔ agents) — style **WhatsApp** : bulles gauche
(agents) / droite (moi), **séparateurs de date** (Aujourd'hui / Hier / …),
images et **messages vocaux** (enregistrement + écoute, avec durée affichée).

## 🏗️ Architecture professionnelle

- **Application factory** + **blueprints** + **couche services** (voir
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).
- **Sécurité** : rate-limit anti force brute, validation des entrées et des
  uploads, en-têtes de sécurité, CORS restreignable, refus de démarrage en
  production non sûre ([docs/SECURITY.md](docs/SECURITY.md)).
- **Optimisations** : index BDD, pagination, stats SQL + cache.
- **Qualité** : 52 tests, migrations Alembic (vérifiées sur PostgreSQL 16),
  CI GitHub Actions, Docker.

## 🚀 Démarrage rapide

```bash
# 0. Base de données PostgreSQL (recommandé) — la plus simple : via Docker
docker compose up -d db             # PostgreSQL sur localhost:5432
export DATABASE_URL="postgresql+psycopg2://safecity:safecity@localhost:5432/safecity"
# (Windows PowerShell : $env:DATABASE_URL="postgresql+psycopg2://safecity:safecity@localhost:5432/safecity")
# Sans PostgreSQL sous la main : ne définissez pas DATABASE_URL (SQLite local).

# 1. Backend (sert AUSSI l'app citoyenne et le portail en développement)
pip install -r requirements.txt
python -m backend.app               # Flask (dev) sur http://localhost:5000
# (prod locale : python -m backend.server — Waitress)

#   → App citoyenne : http://localhost:5000/
#   → Portail agents : http://localhost:5000/portal/
#   (page + API sur la même origine : aucun souci de CORS)

# 2. Poste opérateur (dans un autre terminal)
pip install PySide6 "python-socketio[client]>=5.12"
python -m desktop.main
```

> Astuce : en développement, **inutile de lancer un second serveur** pour le web.
> Le backend sert l'app citoyenne (`/`) et le portail (`/portal/`). Vous pouvez
> quand même les servir séparément si vous préférez :
> `cd web && python -m http.server 8080` (et `portal` sur 8090).
Compte opérateur de démo : `operateur@safecity.local` / `safecity123`

> Le **backend doit tourner** avant le poste opérateur. Les fichiers `web/`
> pointent vers `localhost:5000` (modifiable via `web/js/config.js`).

### Données de démonstration
```bash
python scripts/simulate_alerts.py http://localhost:5000
```

### Docker — démo locale (backend + PostgreSQL + web + portail)
```bash
docker compose up --build        # app :8080 · portail :8090 · api :5000
```

### Docker — PRODUCTION (VPS + Nginx + HTTPS + WebSocket + sauvegardes)
Pile complète pour un serveur (ex. Contabo/Ubuntu) : Nginx (reverse proxy +
TLS), backend Gunicorn/eventlet (vraies websockets), PostgreSQL, certificats
Let's Encrypt et sauvegardes automatiques. Voir **[docs/PRODUCTION.md](docs/PRODUCTION.md)**.
```bash
# Installation automatique (Docker + config + HTTPS) :
sudo bash deploy/install.sh
```

## 🧪 Tests
```bash
pytest -q                      # avec pytest
python tests/test_backend.py   # sans pytest
```

## 🗂️ Structure
```
backend/    API modulaire (factory, blueprints, services, IA, sécurité)
web/        application citoyenne (HTML/CSS/JS + Leaflet)
portal/     portail web des agents d'intervention (temps réel + carte)
desktop/    poste opérateur (PySide6 + Qt WebEngine + Qt Charts)
scripts/    outils (simulation d'alertes)
tests/      tests du backend
docs/       API · ARCHITECTURE · SECURITY · DEPLOYMENT
Dockerfile · docker-compose.yml · Makefile · .env.example
```

## ⚙️ Configuration
Copier `.env.example` en `.env`. Principales variables :

| Variable | Rôle | Défaut |
|----------|------|--------|
| `SAFECITY_ENV` | development / production / testing | development |
| `DATABASE_URL` | Base **PostgreSQL** (`postgresql+psycopg2://…`) | SQLite si vide |
| `SAFECITY_SECRET_KEY` | Clé JWT (obligatoire en prod) | clé de dev |
| `SAFECITY_CORS_ORIGINS` | Origines autorisées | `*` |
| `SAFECITY_SEED_DEMO` | Compte démo (désactiver en prod) | true |

Détails : [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## 📚 Documentation
[Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) ·
[Sécurité](docs/SECURITY.md) · [Déploiement](docs/DEPLOYMENT.md) ·
[Production](docs/PRODUCTION.md) · [**Checklist de déploiement**](docs/DEPLOIEMENT_CHECKLIST.md) ·
[Confidentialité](docs/CONFIDENTIALITE.md) ·
[Contribuer](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## 🩺 Dépannage — la carte ne s'affiche pas (poste opérateur)
- **Leaflet est embarqué localement** (`desktop/vendor/leaflet/`) : la carte et
  les marqueurs fonctionnent **sans Internet**. Seules les **tuiles de fond**
  nécessitent le réseau (un fond uni sombre s'affiche sinon, avec les marqueurs).
- Si la zone affiche « Module carte (Qt WebEngine) indisponible » :
  `pip install PySide6-Addons` (ou `pip install PySide6`), puis relancez.

## 🔒 Avertissement
Prototype à visée pédagogique. Pour une urgence réelle, contactez toujours les
services de secours officiels.
