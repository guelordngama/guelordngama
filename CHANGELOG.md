# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [2.0.0] — Version professionnelle

### Ajouté
- **Architecture modulaire** du backend : application factory, blueprints
  (auth, alerts, teams, stats, health, uploads), couche **services**,
  extensions centralisées.
- **Sécurité renforcée** : limitation du débit anti force brute sur la
  connexion, validation stricte des entrées, validation des uploads
  (extension + taille), en-têtes de sécurité, CORS restreignable, refus de
  démarrage en production non sûre, erreurs JSON homogènes sans fuite de trace.
- **Optimisations** : index de base de données, pagination des alertes,
  statistiques calculées en SQL avec cache court, `pool_pre_ping`.
- **Déploiement** : `Dockerfile`, `docker-compose.yml` (PostgreSQL),
  `.env.example`, `.dockerignore`, `Makefile`, intégration continue GitHub
  Actions (tests + build image).
- **Documentation** : `docs/API.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`
  (mise à jour), `docs/DEPLOYMENT.md` (mise à jour), `CONTRIBUTING.md`,
  `CHANGELOG.md`.
- **Tests** étendus : API, IA, géographie, sécurité, validation (21 tests) +
  fixtures pytest.

### Modifié
- Journalisation structurée.
- Dépendances : bornes de version compatibles, `python-dotenv`.

### Compatibilité
- Les endpoints et les formats JSON restent **identiques** : l'application
  citoyenne (web) et le poste opérateur (PySide6) fonctionnent sans changement.

## [1.x] — Prototype initial
- Backend Flask + Socket.IO, app citoyenne (Leaflet), poste opérateur
  (PySide6 + Qt WebEngine + Qt Charts), IA de classification, temps réel.
- Correctifs : import direct PyCharm, conflit `jwt`/PyJWT, versions
  Flask-SocketIO/python-socketio, transport polling (Waitress).
