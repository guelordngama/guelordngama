# Architecture SafeCity

## Vue d'ensemble

```
┌──────────────────────┐        REST / Socket.IO     ┌───────────────────────────┐
│  📱 App citoyenne     │  ───────────────────────►   │   🌐 Backend Flask (modulaire) │
│  (HTML/CSS/JS,        │                             │   factory + blueprints     │
│   Leaflet)            │  ◄───────────────────────   │   services · IA · sécurité │
└──────────────────────┘                             │                            │
┌──────────────────────┐                             │                            │
│  🖥️ Poste opérateur   │  ◄───────────────────────   │                            │
│  (PySide6 + WebEngine │        REST                 │                            │
│   + Qt Charts)        │  ───────────────────────►   └───────────────────────────┘
└──────────────────────┘                                        │
                                                                 ▼
                                                     ┌───────────────────────────┐
                                                     │  🗄️ SQLite / PostgreSQL    │
                                                     └───────────────────────────┘
```

## Structure modulaire du backend

```
backend/
  __init__.py          Fabrique create_app() + en-têtes de sécurité
  config.py            Configurations (dev/prod/test) + validation
  extensions.py        Instances partagées : db, socketio, cors
  logging_config.py    Journalisation
  errors.py            Exceptions API + gestionnaires d'erreurs JSON
  validation.py        Validation/normalisation des entrées
  security.py          bcrypt, JWT, contrôle d'accès, rate-limit, uploads
  models.py            User, Team, Alert (+ index)
  geo.py               Distance Haversine, ETA, quartier/adresse
  ai/classifier.py     Classification IA (scikit-learn + repli mots-clés)
  seed.py              Données initiales (équipes, compte démo)
  realtime.py          Événements Socket.IO
  services/
    alerts.py          Logique métier des alertes (création, affectation…)
    stats.py           Agrégats du tableau de bord (SQL + cache)
  api/                 Blueprints HTTP (couche fine)
    health.py  auth.py  alerts.py  teams.py  stats.py  uploads.py
  app.py               Instance `app` + serveur de développement
  server.py            Point d'entrée production (Waitress/eventlet)
```

### Principes
- **Application factory** : `create_app(config)` construit une app isolée
  (facilite les tests et le multi-environnement).
- **Blueprints** : chaque domaine (auth, alerts, teams, stats) est un module HTTP
  mince qui délègue à la **couche services**.
- **Services** : toute la logique métier, testable sans HTTP, émet le temps réel.
- **Extensions centralisées** : évite les imports circulaires.
- **Erreurs typées** : `ApiError` → réponses JSON homogènes ; les 500 masquent
  les détails internes.

## Cycle de vie d'une alerte

1. Le citoyen appuie sur 🚨 → GPS récupéré → `POST /api/alerts`.
2. Validation → **IA** (catégorie + urgence) → quartier/adresse → distance/ETA
   → enregistrement → événement `new_alert` diffusé.
3. Le poste opérateur reçoit l'événement, met à jour tableau, carte et stats.
4. `POST /assign` → recalcul distance depuis l'équipe, statut `assignee`.
5. `POST /close` → statut `cloturee`, équipe libérée.

## Modèle de données

| Table | Champs clés | Index |
|-------|-------------|-------|
| `users` | email (unique), password_hash (bcrypt), role | email, role, created_at |
| `teams` | name, patrol_lat/lng, status | — |
| `alerts` | type, lat/lng, urgency, ai_category, status, distance_m… | (status, created_at), (type, created_at), neighborhood |

## Intelligence artificielle

`ai/classifier.py` — **TF-IDF + Naive Bayes** (scikit-learn) entraîné au
démarrage sur un jeu amorce français → catégorie ; score d'urgence combinant
catégorie et mots-clés de gravité. **Repli par mots-clés** si scikit-learn
absent : le backend reste fonctionnel.

## Voir aussi
- [API.md](API.md) — référence des endpoints
- [SECURITY.md](SECURITY.md) — sécurité et durcissement
- [DEPLOYMENT.md](DEPLOYMENT.md) — mise en production
