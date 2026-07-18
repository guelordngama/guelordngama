# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [2.2.0] — Rapports PDF & application citoyenne modernisée

### Ajouté
- **Génération de rapports PDF** (reportlab) : endpoint `GET /api/reports/pdf`
  (périodes aujourd'hui/mois/année/tout), synthèse (KPIs, incidents par type et
  par commune, détail des alertes). Bouton « Générer le PDF » dans le poste
  opérateur (choix de la période, enregistrement + ouverture automatique).
- **Application citoyenne modernisée** : thème sombre, dégradés et lueurs,
  effet verre (glassmorphism), bouton d'alerte animé, champs **nom** et
  **téléphone** du citoyen (transmis à l'opérateur et affichés dans le pop-up
  d'incident).

## [2.1.0] — Poste opérateur « centre de commandement »

### Ajouté
- **Interface bureau repensée** (PySide6, thème sombre) inspirée des centres de
  commandement : menu latéral (tableau de bord, alertes en direct, carte,
  agents, citoyens, historique, statistiques, rapports, paramètres,
  déconnexion), coins arrondis, ombres, badges colorés.
- **Tableau de bord** : tuiles (alertes du jour, en cours, résolues, agents
  connectés), graphiques (répartition par type, zones à risque), dernières
  alertes.
- **Pop-up d'incident automatique** à l'arrivée d'une alerte : **alarme sonore**
  (synthétisée), notification visuelle (toast), informations (citoyen,
  téléphone, heure, GPS, urgence, média) et actions **Accepter / Envoyer une
  patrouille / Appeler / Ouvrir la carte / Clôturer**.
- **Carte interactive** sombre, marqueurs colorés par gravité (🟢🟡🟠🔴),
  positions des patrouilles, légende.
- **Statistiques** : temps de réponse moyen, incidents par commune, types
  fréquents, résolues du jour.
- **Rôles et permissions** : admin, superviseur, opérateur, agent, citoyen.
- Backend : endpoints `/api/agents` et `/api/citizens`, statistiques enrichies
  (résolues, temps de réponse, agents connectés, par commune), infos citoyen
  (nom/téléphone) sur les alertes, suivi du nombre d'agents connectés en direct.

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
