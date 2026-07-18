# 🛡️ SafeCity — Plateforme d'alerte citoyenne

Application professionnelle de sécurité urbaine : un citoyen signale un danger
en un geste depuis son téléphone, et le centre de surveillance de la mairie
reçoit, localise et traite l'alerte **en temps réel**.

```
📱 App citoyenne (Web)  ──►  🌐 Backend Flask modulaire  ──►  🖥️ Poste opérateur (PySide6)
   Alerte + GPS + IA          factory · blueprints · services     Tableau de bord · Carte · Actions
```

## ✨ Fonctionnalités

**Application citoyenne** (`web/`) — bouton d'alerte, GPS automatique, type de
danger (vol, braquage, incendie, accident, violence, autre), photo, message
vocal, distance/ETA, confirmation avec carte OpenStreetMap.

**Backend** (`backend/`) — API REST + temps réel Socket.IO, **classification IA**
des incidents (scikit-learn), calcul de distance (Haversine) et d'ETA,
authentification bcrypt + JWT, base SQLite (dev) / PostgreSQL (prod).

**Poste opérateur** (`desktop/`) — tableau de bord, alertes en direct, carte
interactive (Qt WebEngine + Leaflet), graphiques (Qt Charts), actions
**Voir sur la carte / Affecter une équipe / Clôturer**.

## 🏗️ Architecture professionnelle

- **Application factory** + **blueprints** + **couche services** (voir
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).
- **Sécurité** : rate-limit anti force brute, validation des entrées et des
  uploads, en-têtes de sécurité, CORS restreignable, refus de démarrage en
  production non sûre ([docs/SECURITY.md](docs/SECURITY.md)).
- **Optimisations** : index BDD, pagination, stats SQL + cache.
- **Qualité** : 21 tests, CI GitHub Actions, Docker.

## 🚀 Démarrage rapide

```bash
# 1. Backend
pip install -r requirements.txt
python -m backend.server            # Waitress sur http://localhost:5000
# (dev : python -m backend.app)

# 2. Application citoyenne
cd web && python -m http.server 8080

# 3. Poste opérateur (dans un autre terminal)
pip install PySide6 "python-socketio[client]>=5.12"
python -m desktop.main
```
Compte opérateur de démo : `operateur@safecity.local` / `safecity123`

> Le **backend doit tourner** avant le poste opérateur. Les fichiers `web/`
> pointent vers `localhost:5000` (modifiable via `web/js/config.js`).

### Données de démonstration
```bash
python scripts/simulate_alerts.py http://localhost:5000
```

### Docker (backend + PostgreSQL)
```bash
export SAFECITY_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SAFECITY_CORS_ORIGINS="https://mon-domaine.org"
docker compose up --build -d
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
| `DATABASE_URL` | Base de données | SQLite local |
| `SAFECITY_SECRET_KEY` | Clé JWT (obligatoire en prod) | clé de dev |
| `SAFECITY_CORS_ORIGINS` | Origines autorisées | `*` |
| `SAFECITY_SEED_DEMO` | Compte démo (désactiver en prod) | true |

Détails : [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## 📚 Documentation
[Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) ·
[Sécurité](docs/SECURITY.md) · [Déploiement](docs/DEPLOYMENT.md) ·
[Contribuer](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## 🔒 Avertissement
Prototype à visée pédagogique. Pour une urgence réelle, contactez toujours les
services de secours officiels.
