# Architecture SafeCity

## Vue d'ensemble

```
┌──────────────────────┐        HTTPS / REST        ┌───────────────────────────┐
│  📱 App citoyenne     │  ───────────────────────►  │   🌐 Backend Flask         │
│  (HTML/CSS/JS,        │        Socket.IO           │   - REST API               │
│   Leaflet)            │  ◄───────────────────────  │   - Flask-SocketIO         │
│  GPS · photo · voix   │                            │   - SQLAlchemy (BDD)       │
└──────────────────────┘                            │   - IA (scikit-learn)      │
                                                     │   - Auth bcrypt + JWT      │
┌──────────────────────┐        Socket.IO           │                            │
│  🖥️ Poste opérateur   │  ◄───────────────────────  │                            │
│  (PySide6 + WebEngine │        REST                │                            │
│   + Qt Charts)        │  ───────────────────────►  │                            │
│  tableau · carte      │                            └───────────────────────────┘
└──────────────────────┘                                        │
                                                                 ▼
                                                     ┌───────────────────────────┐
                                                     │  🗄️ SQLite / PostgreSQL    │
                                                     └───────────────────────────┘
```

## Cycle de vie d'une alerte

1. **Citoyen** ouvre l'app → appuie sur 🚨 ALERTE.
2. Le navigateur récupère la **position GPS**.
3. Choix du **type de danger** (+ description, photo, audio optionnels).
4. `POST /api/alerts` → le backend :
   - classe l'incident via l'**IA** (catégorie + urgence) ;
   - résout **quartier / adresse** ;
   - calcule **distance & ETA** depuis la patrouille ;
   - enregistre en base ;
   - **diffuse** `new_alert` à la salle `surveillance` via Socket.IO.
5. Le **poste opérateur** reçoit l'événement, met à jour le tableau, la carte et les stats.
6. L'opérateur **affecte une équipe** (`/assign`) → recalcul de distance depuis la position de l'équipe, statut `assignee`, événement `alert_updated`.
7. L'opérateur **clôture** (`/close`) → statut `cloturee`, équipe libérée.

## Modèle de données

| Table | Champs principaux |
|-------|-------------------|
| `users` | name, email, password_hash (bcrypt), role (`citizen`/`operator`/`admin`) |
| `teams` | name, patrol_lat, patrol_lng, status (`available`/`busy`) |
| `alerts` | type, description, lat, lng, address, neighborhood, photo/audio, **urgency**, **ai_category**, ai_score, status, assigned_team, distance_m, eta_moto/walk, timestamps |

## API REST

| Méthode | Endpoint | Auth | Rôle |
|---------|----------|------|------|
| GET | `/api/health` | — | Sonde de vie |
| GET | `/api/meta` | — | Types de danger / statuts |
| POST | `/api/auth/login` | — | Connexion opérateur → JWT |
| POST | `/api/alerts` | — | Créer une alerte (citoyen) |
| GET | `/api/alerts` | — | Lister (filtre `?status=`) |
| GET | `/api/alerts/<id>` | — | Détail |
| GET | `/api/stats` | — | Statistiques tableau de bord |
| GET | `/api/teams` | — | Équipes |
| POST | `/api/alerts/<id>/assign` | JWT | Affecter une équipe |
| POST | `/api/alerts/<id>/close` | JWT | Clôturer |

## Événements Socket.IO (salle `surveillance`)

| Événement | Sens | Charge utile |
|-----------|------|--------------|
| `new_alert` | serveur → opérateurs | alerte complète |
| `alert_updated` | serveur → opérateurs | alerte mise à jour |
| `connected` | serveur → client | message de bienvenue |

## Intelligence artificielle

`backend/ai/classifier.py` :
- **TF-IDF + Naive Bayes** (scikit-learn) entraîné au démarrage sur un jeu
  amorce en français → catégorie de l'incident.
- **Score d'urgence** combinant la catégorie et des mots-clés de gravité
  (armé, feu, blessé…) → `faible` / `moyenne` / `haute` / `critique`.
- **Repli automatique** par mots-clés si scikit-learn est absent : le backend
  reste fonctionnel en toute circonstance.
- La clé/API IA (le cas échéant) reste **côté serveur**, jamais dans le client.

## Calcul de distance & temps d'intervention

`backend/geo.py` — formule de **Haversine** entre la patrouille et l'alerte,
puis ETA selon des vitesses moyennes (moto 25 km/h, marche 5 km/h). Exemple :

```
Patrouille : Avenue Lumumba
Alerte     : Quartier Kenya
Distance   : 850 m
Temps est. : ~2 min en moto · ~5 min à pied
```
