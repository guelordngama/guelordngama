# 🛡️ SafeCity — Plateforme d'alerte citoyenne

SafeCity permet à un citoyen de signaler un danger en un geste depuis son
téléphone, et au centre de surveillance de la mairie de recevoir, localiser et
traiter l'alerte **en temps réel**.

```
📱 App citoyenne (Web)  ──►  🌐 Backend Flask + Socket.IO  ──►  🖥️ Poste opérateur (PySide6)
   Alerte + GPS + IA          API REST · IA · Base de données      Tableau de bord · Carte · Actions
```

## ✨ Fonctionnalités

### Application citoyenne (`web/`)
- 🚨 Gros bouton d'alerte d'urgence
- 📍 Récupération automatique de la position GPS
- ⚠️ Sélection du type de danger : vol, braquage, incendie, accident, violence, autre
- 📷 Ajout d'une photo · 🎤 message vocal (optionnel)
- 📏 Distance et temps d'intervention estimés (moto / à pied)
- 📍 Affichage du quartier et de l'adresse
- 🔔 Écran de confirmation avec mini-carte OpenStreetMap

### Backend (`backend/`)
- API REST Flask + temps réel **Flask-SocketIO**
- **Classification IA** des incidents (scikit-learn : catégorie + niveau d'urgence)
- Calcul de distance (Haversine) et d'ETA depuis la patrouille
- Authentification opérateur : **bcrypt** + **JWT**
- Base de données **SQLite** (prototype) ou **PostgreSQL** (production) via SQLAlchemy
- Statistiques pour le tableau de bord (alertes du jour, zones dangereuses…)

### Application bureau — Centre de surveillance (`desktop/`)
- Tableau de bord : alertes du jour, actives, zones dangereuses, total
- 🔴 Alertes **en direct** (heure, type, quartier, distance, urgence, statut)
- 🗺️ Carte interactive **OpenStreetMap** (Qt WebEngine + Leaflet), marqueurs colorés par urgence
- 📊 Graphique **Qt Charts** (répartition par type)
- Actions opérateur : **📍 Voir sur la carte**, **🚔 Affecter une équipe**, **✅ Clôturer**

## 🚀 Démarrage rapide

### 1. Backend
```bash
pip install -r requirements.txt
python -m backend.server            # Waitress sur http://localhost:5000
# ou, en développement :
python -m backend.app               # serveur Flask + Socket.IO
```
Compte opérateur de démonstration : `operateur@safecity.local` / `safecity123`

### 2. Application citoyenne
```bash
cd web
python -m http.server 8080          # http://localhost:8080
```
> Pour pointer vers un autre backend, ouvrez la console du navigateur :
> `localStorage.setItem('safecity_api', 'http://mon-serveur:5000')`

### 3. Poste opérateur (bureau)
```bash
pip install PySide6
python -m desktop.main
```

### 4. Données de démonstration
```bash
python scripts/simulate_alerts.py http://localhost:5000
```

## 🧪 Tests
```bash
python tests/test_backend.py        # sans pytest
# ou
pip install pytest && pytest -q
```

## 🗂️ Structure du projet
```
backend/            API Flask, temps réel, IA, base de données
  app.py            application + routes REST + événements Socket.IO
  models.py         User, Team, Alert (SQLAlchemy)
  auth.py           bcrypt + JWT
  geo.py            distance Haversine, ETA, quartier/adresse
  ai/classifier.py  classification IA des incidents (scikit-learn)
  server.py         point d'entrée production (Waitress)
  config.py         configuration (SQLite / PostgreSQL)
web/                application citoyenne (HTML/CSS/JS + Leaflet)
desktop/            poste opérateur (PySide6 + Qt WebEngine + Qt Charts)
scripts/            outils (simulation d'alertes)
tests/              tests du backend
docs/               architecture & déploiement
```

## ⚙️ Configuration (variables d'environnement)
| Variable | Rôle | Défaut |
|----------|------|--------|
| `DATABASE_URL` | Base de données | `sqlite:///backend/safecity.db` |
| `SAFECITY_SECRET_KEY` | Clé de signature JWT | clé de dev |
| `SAFECITY_PORT` | Port du serveur | `5000` |
| `SAFECITY_SERVER` | `waitress` ou `socketio` | `waitress` |
| `SAFECITY_ASYNC_MODE` | mode Socket.IO (`threading`/`eventlet`) | `threading` |
| `SAFECITY_PATROL_LAT` / `_LNG` | patrouille par défaut | Kinshasa |

Voir [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) et
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) pour le détail.

## 🔒 Sécurité & remarques
- Les mots de passe sont hachés avec **bcrypt** ; les endpoints sensibles exigent un **JWT**.
- La clé IA / secrets restent **côté serveur** (jamais dans le code client).
- Prototype à visée pédagogique — pour une urgence réelle, contactez toujours
  les services de secours officiels.
