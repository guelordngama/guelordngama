# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [3.1.0] — Guide utilisateur final (soutenance)

### Ajouté
- **Guide utilisateur final** prêt pour la soutenance :
  - `docs/guide.html` — guide autonome (captures d'écran intégrées) mis en page
    pour l'impression A4 : page de couverture (SafeCity Lubumbashi, Guelord
    Ngama Wa Ngama, version 1.0.0, 2026), sommaire, présentation, architecture,
    installation, comptes de démonstration, mode d'emploi des 3 applications
    (app citoyenne, poste opérateur, portail agents), récapitulatif des
    fonctionnalités, sécurité & sauvegardes.
  - `docs/SafeCity_Guide_Utilisateur.pdf` — version PDF imprimable du guide.

## [3.0.0] — Architecture de production (VPS + Nginx + HTTPS + WebSocket)

### Ajouté
- **Pile de production Docker** (`docker-compose.prod.yml`) pour un VPS
  (ex. Contabo/Ubuntu) :
  - **Nginx** en reverse proxy : TLS/HTTPS, sert l'app citoyenne (`/`) et le
    portail agents (`/portal/`), proxifie `/api`, `/uploads` et `/socket.io`
    (avec montée en **WebSocket**).
  - **Backend Gunicorn + eventlet** (`backend/wsgi.py`) : vraies websockets
    Socket.IO en production.
  - **PostgreSQL** (volume persistant).
  - **Certbot** : émission (`deploy/init-letsencrypt.sh`) et renouvellement
    automatique des certificats Let's Encrypt.
  - **Sauvegardes automatiques** PostgreSQL (`deploy/backup.sh` : pg_dump
    périodique + rotation).
- Commande d'administration `python -m backend.manage create-admin` (créer un
  vrai administrateur) et `list-staff`.
- Fronts « même origine » (config auto : localhost en dev, origine du serveur en
  prod via Nginx) ; montée en WebSocket côté navigateur avec repli polling.
- **Script d'installation unique** `deploy/install.sh` : installe Docker,
  génère la configuration de production de façon interactive (domaine sslip.io
  + secrets générés automatiquement), ouvre les ports, émet le certificat HTTPS
  et démarre toute la pile — en une commande sur le VPS.
- Guide **docs/PRODUCTION.md** (déploiement pas à pas, sslip.io pour HTTPS sans
  domaine acheté).

### Modifié
- Le compte de démonstration en production n'est plus bloquant mais génère un
  **avertissement** (permet un premier démarrage, à désactiver ensuite).

## [2.12.0] — Historique des interventions par agent

### Ajouté
- **Historique des interventions par agent** :
  - Poste opérateur : bouton « 📜 Interventions » (page Gestion des agents) →
    fenêtre listant les interventions de l'agent (date, type, quartier, urgence,
    statut, distance) avec résumé (total, résolues, temps de réponse, distance).
  - Portail agents : bouton « 📜 Mes interventions » → fenêtre modale de son
    propre historique.
  - Endpoints `GET /api/agents/<id>/interventions` (opérateur) et
    `GET /api/agents/me/interventions` (agent).

## [2.11.0] — Assignation d'une alerte à un agent précis

### Ajouté
- L'opérateur peut **assigner une alerte à un agent précis** depuis la page
  « Alertes en direct » (bouton « 👮 Affecter un agent » + sélecteur d'agent
  avec disponibilité). L'agent concerné reçoit l'alarme « intervention
  assignée » et l'itinéraire dans son portail. Endpoint
  `POST /api/alerts/<id>/assign-agent` (opérateur/superviseur/admin).

## [2.10.0] — Terminer l'intervention côté agent

### Ajouté
- Bouton **« 🏁 Terminer l'intervention »** dans le portail agents : l'agent
  clôture depuis le terrain l'intervention qui lui est assignée. Il redevient
  automatiquement « disponible » et l'itinéraire est effacé. Endpoint
  `POST /api/alerts/<id>/complete` (l'agent ne peut terminer que SA propre
  intervention).

## [2.9.0] — Notifications sonores du portail agents

### Ajouté
- **Sons de notification dans le portail agents** :
  - **Alarme** (+ vibration + toast) à la réception d'une nouvelle alerte.
  - **Alarme renforcée** lorsqu'une intervention est assignée à l'agent
    (itinéraire tracé automatiquement, statut passé en « en intervention »).
  - **Son d'accusé de réception** lorsque l'agent accepte une intervention.
  - **Bip discret** à la réception d'un message du centre.
- Notifications visuelles (toasts) dans le portail agents.

## [2.7.0] — Pièces jointes, mode hors-ligne & déploiement Docker complet

### Ajouté
- **Pièces jointes dans la messagerie** : envoi et affichage d'images (poste
  opérateur via 📎 + lien ; portail agents via 📎 + miniature cliquable).
  Endpoint `POST /api/messages` accepte `attachment` (image base64).
- **Mode hors-ligne de l'app citoyenne** : si le réseau est absent, l'alerte
  est **enregistrée localement** et **renvoyée automatiquement** au retour de la
  connexion (file d'attente locale + verrou anti-doublon + bandeau « en
  attente »). Service worker + manifest pour un chargement hors-ligne (PWA).
- **Déploiement Docker complet en une commande** (`docker compose up`) :
  PostgreSQL + backend + **app citoyenne** (8080) + **portail agents** (8090).

### Corrigé
- Envoi en double des alertes en attente lorsqu'un `online` et l'intervalle de
  renvoi se déclenchaient simultanément (verrou de vidage de file).

## [2.6.0] — Messagerie temps réel & export Excel/CSV

### Ajouté
- **Messagerie temps réel** opérateurs ↔ agents : nouvel onglet « Messagerie »
  (poste opérateur) et panneau de discussion dans le portail agents, diffusion
  instantanée via Socket.IO, historique persistant. Endpoints
  `GET/POST /api/messages`.
- **Export Excel / CSV** des historiques d'alertes (respecte les filtres) :
  boutons « Exporter CSV » et « Exporter Excel » sur la page Historique.
  Endpoints `GET /api/export/alerts.csv` et `/api/export/alerts.xlsx`
  (openpyxl ; CSV avec BOM pour Excel).

## [2.5.0] — Itinéraire le plus rapide & notifications push

### Ajouté
- **Itinéraire le plus rapide** tracé sur la carte entre un agent et l'incident
  qu'il traite (routage réel via OSRM, repli sur trajet direct) avec distance et
  durée estimées. Bouton « 🧭 Itinéraire » (poste opérateur) ; tracé automatique
  dans le portail agents à la prise en charge d'une alerte.
- **Notifications push** à l'arrivée d'une alerte (par défaut urgences Élevé /
  Critique) : **e-mail** (SMTP) et **SMS** (Twilio), envoi non bloquant en
  arrière-plan, activés uniquement si configurés (voir `.env.example`).

## [2.4.0] — Gestion complète des agents

### Ajouté
- **CRUD des agents** depuis le poste opérateur (onglet « Gestion des agents ») :
  **Ajouter**, **Modifier**, **Supprimer** un agent via un formulaire dédié
  (nom, email, téléphone, rôle, mot de passe, actif). Endpoints
  `POST/PATCH/DELETE /api/agents`.
- **Localiser un agent** sur la carte : bouton « 📍 Localiser » qui centre la
  carte sur la position terrain de l'agent.
- Validations serveur (email unique, mot de passe ≥ 6, rôle valide) ; interdiction
  de supprimer son propre compte ; détachement des alertes de l'agent supprimé ;
  diffusion temps réel des créations/suppressions d'agents.

## [2.3.0] — Recherche avancée, portail agents & analyse de performance

### Ajouté
- **Recherche avancée** (poste opérateur) : filtres par catégorie, urgence,
  statut, localisation, dates, et recherche texte (citoyen, téléphone, quartier,
  description). Endpoint `GET /api/alerts` étendu.
- **Portail web sécurisé des agents** (`portal/`) : connexion JWT, alertes en
  direct (Socket.IO), carte, prise en charge d'intervention, envoi automatique
  de la position GPS, bascule de disponibilité, notification sonore + vibration.
- **Suivi opérationnel des agents** (superviseur) : page « Gestion des agents »
  avec disponibilité, position GPS, intervention en cours et dernière activité,
  mise à jour en temps réel ; marqueurs agents sur la carte.
- **Module d'analyse de performance** (« Performances ») : indicateurs hebdo/
  mensuel/annuel — interventions, taux de résolution, temps de réponse moyen,
  distance parcourue, classement par agent. Endpoint `GET /api/analytics`.
- Backend : prise en charge d'intervention (`POST /api/alerts/<id>/accept`),
  suivi agent (`/api/agents/me/location`, `/api/agents/me/status`), champs de
  suivi (position, disponibilité, distance cumulée) et affectation d'agent.

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
