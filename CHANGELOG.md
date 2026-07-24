# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [1.1.0] — 2026-07-24 — Messagerie enrichie & tableau de bord

Version **rétro-compatible** avec la 1.0.0 (aucun changement cassant). Elle
enrichit la messagerie et le tableau de bord du poste opérateur. Le détail
figure dans les entrées `3.13.x`–`3.15.x` ci-dessous ; récapitulatif :

### Ajouté
- **Messages vocaux** dans la messagerie interne (opérateurs ↔ agents) :
  enregistrement et écoute sur le **portail agents** (web) comme sur le **poste
  opérateur** (bureau, QtMultimedia), avec **durée affichée** dans la bulle
  (« ▶ Message vocal · 0:12 »).
- **Séparateurs de date façon WhatsApp** dans la messagerie (Aujourd'hui / Hier /
  jour de la semaine / date complète), sur le bureau et le portail.
- **Tableau de bord peaufiné** (bureau) : en-tête d'accueil (salutation + date),
  pastille de situation (🟢/🟠/🔴), tuiles cliquables et sous-titres contextuels.

### Base de données
- Nouvelles colonnes `messages.voice_path` et `messages.voice_duration`
  (**migrations Alembic** `b3d7e1f2a9c4` et `c4e8f2a1b6d7`). Appliquer
  `flask db upgrade` au déploiement. **Vérifié sur PostgreSQL 16**
  (upgrade/downgrade/re-upgrade idempotents, lecture/écriture ORM OK).

### Documentation
- `docs/TEST_BUREAU_CHECKLIST.md` : checklist de test du poste opérateur (dont
  les messages vocaux et l'affichage de la durée).

## [1.0.0] — 2026-07-24 — 🎉 Première version de production

Première version **prête pour un déploiement réel** (mairie / centre de
surveillance). Elle consolide tout le développement décrit ci-dessous (versions
2.x et 3.x) en un produit cohérent et professionnel.

**Plateforme complète**
- **App citoyenne** (web/PWA) : compte + vérification du téléphone par **SMS
  (OTP)**, bouton d'alerte, GPS, type de danger, photo, message vocal, mode
  hors-ligne, thème clair/sombre, mot de passe oublié par SMS.
- **Poste opérateur** (bureau, PySide6) : tableau de bord, alertes en direct,
  carte, gestion des agents, messagerie type WhatsApp, pop-up d'incident avec
  minuteur, sons, marquage non lu, barre d'état, raccourcis, thèmes.
- **Portail agents** (web) : alertes temps réel, carte, prise en charge,
  messagerie, sons de notification fiabilisés, thèmes.
- **Backend** (Flask) : API REST + temps réel Socket.IO, **classification IA**,
  distance/ETA, **PostgreSQL**, **migrations Alembic**.

**Sécurité & conformité**
- bcrypt + JWT, limitation anti force brute, journal d'**audit**, création de
  comptes personnels par **code d'invitation**, changement de mot de passe.
- **Vérification du téléphone par SMS** (Africa's Talking / passerelle générique).
- **Politique de confidentialité**, consentement, **droit à l'effacement**,
  purge de conservation des données.

**Exploitation**
- Déploiement Docker (Nginx + HTTPS Let's Encrypt + PostgreSQL + sauvegardes),
  **script d'installation unique**, **suivi d'erreurs (Sentry)**, restauration
  testée, **checklist de déploiement** pas à pas.

Voir le détail des évolutions dans les entrées ci-dessous.

## [3.15.1] — Durée affichée sur les messages vocaux

### Ajouté
- **Durée du vocal** affichée dans la bulle : « ▶ Message vocal · 0:12 » sur le
  **poste opérateur** et « 🎤 Message vocal · 0:12 » sur le **portail agents**.
- La durée est mesurée à l'enregistrement et transmise au serveur
  (nouveau champ `voice_duration`, colonne `messages.voice_duration` +
  **migration Alembic** `c4e8f2a1b6d7`), ce qui garantit un affichage exact et
  évite le défaut connu des fichiers WebM (durée « Infinity ») dans les
  navigateurs. Repli web : lecture de la durée via l'élément `<audio>` si elle
  n'a pas été fournie.

### Vérifié
- **Migrations testées sur PostgreSQL 16** : `flask db upgrade` applique la
  chaîne complète sans erreur (baseline → `consent_at` → `voice_path`
  `b3d7e1f2a9c4` → `voice_duration` `c4e8f2a1b6d7`). Colonnes créées avec les
  bons types (`voice_path` `varchar(255)`, `voice_duration` `integer`),
  `downgrade` et ré-`upgrade` idempotents, et écriture/lecture des colonnes
  vocales validée via l'ORM.

## [3.15.0] — Messages vocaux dans la messagerie

### Ajouté
- **Messages vocaux** dans la messagerie interne (opérateurs ↔ agents), en plus
  du texte et des images :
  - **Portail agents (web)** : bouton 🎤 pour enregistrer (indicateur rouge +
    minuteur, limite de 2 min), pré-écoute avant envoi, et lecture intégrée des
    vocaux reçus (`<audio controls>`). Le bouton se masque si le navigateur ne
    gère pas la capture audio.
  - **Poste opérateur (bureau)** : bouton 🎤 (via QtMultimedia) pour enregistrer
    et envoyer un vocal, et bouton **« ▶ Message vocal »** pour écouter les
    vocaux reçus. Le bouton d'enregistrement n'apparaît que si un micro est
    disponible sur la machine.
- **Backend** : les messages acceptent désormais un champ `voice` (data URL
  audio, formats `webm/ogg/mp3/wav/m4a`), stocké comme fichier et exposé via
  `voice_url`. Nouvelle colonne `messages.voice_path` + **migration Alembic**
  (`b3d7e1f2a9c4`). Un message peut ne contenir qu'un vocal.

## [3.14.0] — Séparateurs de date dans la messagerie (poste opérateur + portail agents)

### Ajouté
- **Pastilles de date façon WhatsApp** dans la messagerie : une étiquette
  centrée (**Aujourd'hui**, **Hier**, le **jour de la semaine** pour les 6
  derniers jours, sinon la **date complète** « 24 juillet 2026 ») s'affiche avant
  le premier message de chaque journée. L'heure de chaque message reste indiquée
  sous la bulle. Fonctionne aussi bien au chargement qu'à l'arrivée d'un nouveau
  message en temps réel. Présent à la fois sur le **poste opérateur** (bureau) et
  sur le **portail agents** (web), pour une expérience cohérente.

## [3.13.0] — Tableau de bord peaufiné (poste opérateur)

### Ajouté
- **En-tête d'accueil** : salutation contextuelle selon l'heure
  (Bonjour / Bon après-midi / Bonsoir) et **date du jour** en clair.
- **Pastille de situation** en haut à droite : 🟢 « Situation calme »,
  🟠 « N intervention(s) en cours » ou 🔴 « N alertes actives » selon le nombre
  d'alertes en cours — état opérationnel visible d'un coup d'œil.
- **Sous-titres contextuels** sous chaque tuile de statistique (ex. taux de cas
  traités, « Aucun agent en ligne », « À suivre en priorité »).

### Modifié
- **Tuiles de statistique cliquables** : cliquer sur « Alertes … » ouvre la vue
  « Alertes en direct », « Agents connectés » ouvre la gestion des agents
  (curseur main au survol).

## [3.12.0] — Pop-up d'incident repensé (poste opérateur)

### Modifié
- **Pop-up d'incident plus professionnel et opérationnel** :
  - **Minuteur en direct** « Reçue il y a MM:SS — délai de réponse en cours »
    (sensibilise au temps de réponse), heure de réception dans le bandeau.
  - **Miniature de la photo** jointe, chargée en arrière-plan (non bloquant).
  - Mise en page soignée : infos à gauche / photo à droite, description en carte,
    action **« Accepter l'intervention »** mise en avant, puis patrouille / agent /
    appeler / carte / clôturer.
  - Fenêtre autonome (applique son propre thème) — cohérente en clair et sombre.

## [3.11.0] — Finitions professionnelles du poste opérateur

### Ajouté
- **Barre d'état** en bas de fenêtre : état de connexion, compteurs en direct
  (alertes du jour · en cours · résolues · agents connectés) et heure de
  **dernière mise à jour**.
- **Bouton couper/activer le son** 🔊/🔇 dans la barre supérieure (préférence
  mémorisée) ; les notifications sonores respectent ce réglage.
- **Raccourcis clavier** : `Ctrl+1…9`/`Ctrl+0` (naviguer entre les sections),
  `F5` (actualiser), `Ctrl+F` (recherche d'alertes), `Ctrl+M` (couper le son).
- **Icône d'application** SafeCity (bouclier) sur la fenêtre et la barre des tâches.
- **État vide** clair sur la liste des alertes (« Aucune alerte en cours »).
- Titre de fenêtre personnalisé (nom de l'opérateur) et **taille minimale**.

## [3.10.1] — Sons de notification fiabilisés (portail agents)

### Corrigé / Ajouté
- **Sons de notification du portail agents fiabilisés** (nouvelle alerte et
  nouveau message) : un **contexte audio unique** est désormais **débloqué à la
  première interaction** (clic « Se connecter » / clic / touche) et **repris s'il
  est suspendu** — corrige l'absence de son due à la politique d'autoplay des
  navigateurs (l'ancien code recréait un contexte suspendu à chaque son).
- **Bip de message plus audible** (double ton + courte vibration) et alarme
  d'alerte renforcée.
- **Notifications système** (API Notification) affichées pour une nouvelle
  alerte ou un nouveau message **quand l'onglet est en arrière-plan** (permission
  demandée à la connexion) — l'agent est prévenu même sans regarder le portail.

## [3.10.0] — Authentification citoyenne de niveau professionnel

### Ajouté
- **Mot de passe oublié par SMS** (citoyen) : « Mot de passe oublié ? » →
  saisie du numéro → code SMS → nouveau mot de passe → connexion automatique.
  Endpoints `POST /api/auth/forgot-password-sms` et `/reset-password-sms`
  (réutilisent l'infrastructure OTP ; réponse générique anti-énumération).
- **Expérience d'inscription/connexion professionnelle** (site citoyen) :
  - **Afficher / masquer** le mot de passe (icône œil).
  - **Indicateur de robustesse** du mot de passe (Très faible → Fort).
  - **Confirmation du mot de passe** + **validation en direct par champ**
    (numéro valide, correspondance des mots de passe, consentement).
  - **Boutons avec indicateur de chargement** (spinner) pendant les requêtes.
  - **Saisie du code en 6 cases** (avance/retour automatiques, collage, envoi
    auto quand complet) + **compte à rebours** avant de pouvoir renvoyer le code.
- Tests backend étendus (réinitialisation par SMS) — 52 au total.
- **Portail agents** : mêmes finitions professionnelles sur la connexion —
  **afficher/masquer le mot de passe**, **spinner de chargement**, et **mot de
  passe oublié par e-mail** (`POST /api/auth/forgot-password`, les agents ayant
  une adresse e-mail) avec écran dédié et retour à la connexion.
- **Poste opérateur** : bouton **œil afficher/masquer** sur les champs mot de
  passe (connexion et création de compte) et **état « chargement »** des boutons
  (« Connexion… » / « Création… ») pendant l'appel réseau.

## [3.9.1] — PostgreSQL comme base de données standard

### Modifié
- **PostgreSQL** est désormais la base de données de référence (dev + prod). Le
  driver `psycopg2-binary` fait partie des dépendances installées par défaut.
  Démarrage local simple : `docker compose up -d db` puis `DATABASE_URL=…`.
  SQLite reste un repli local sans installation et sert aux tests automatiques.
- `.env.example` et le README mis à jour (PostgreSQL en tête). Migrations Alembic
  vérifiées sur PostgreSQL 16 (baseline + `consent_at` appliquées sans erreur).

## [3.9.0] — Thème clair/sombre & son de réception

### Ajouté
- **Thème clair / sombre commutable** sur les trois applications :
  - **Site citoyen** et **portail agents** : bouton 🌙/☀️ (préférence mémorisée
    dans le navigateur) qui bascule le thème via `data-theme` (variables CSS).
  - **Poste opérateur** : bouton dans la barre supérieure ; deux palettes
    (`theme.set_mode`) appliquées à chaud à toute l'interface, préférence
    mémorisée (QSettings).
- **Son de réception des messages** dans le poste opérateur : un « ping » discret
  accompagne le badge et la notification (toast) à l'arrivée d'un message.

## [3.8.1] — Connecteur SMS Africa's Talking

### Ajouté
- **Connecteur SMS Africa's Talking** (couverture RDC) pour l'envoi des codes de
  vérification (OTP), sans dépendance supplémentaire. Configuration
  `SAFECITY_AT_USERNAME` / `SAFECITY_AT_API_KEY` (+ sender ID et mode bac à sable
  optionnels). Vérifie le statut de livraison renvoyé par l'API et lève une
  erreur claire en cas de refus. Priorité : Africa's Talking → passerelle HTTP
  générique → Twilio. Documentation et checklist mises à jour.

## [3.8.0] — Conformité & confidentialité

### Ajouté
- **Politique de confidentialité** (`docs/CONFIDENTIALITE.md`) + **modale** dans
  l'app citoyenne (données collectées, finalités, accès, conservation, droits).
- **Consentement obligatoire** à l'inscription : case à cocher « J'accepte la
  politique de confidentialité » (bloquante côté app et côté serveur), date de
  consentement enregistrée (`consent_at`).
- **Droit à l'effacement** : bouton « Supprimer mon compte » dans l'app citoyenne
  → `DELETE /api/auth/me`. Les données personnelles sont supprimées et les
  incidents déjà signalés **anonymisés** (conservés sans nom ni téléphone).
- **Conservation des données** : commande `python -m backend.manage purge-old`
  (+ `SAFECITY_RETENTION_DAYS`) qui supprime les alertes clôturées anciennes et
  leurs fichiers joints (à planifier via cron). Migration Alembic pour
  `consent_at` (évolution sans perte).

## [3.7.0] — Fiabilité : migrations, suivi d'erreurs, restauration

### Ajouté
- **Migrations de schéma (Alembic via Flask-Migrate)** : le schéma évolue
  désormais **sans perte de données**. En production, le conteneur backend
  applique automatiquement `flask db upgrade` au démarrage ; en dev/test,
  `create_all()` reste utilisé pour un démarrage immédiat. Migration initiale
  (`migrations/versions/…_baseline_schema.py`) couvrant tout le schéma actuel.
- **Suivi d'erreurs (Sentry)** : alerte automatique en cas d'erreur serveur en
  production (`SAFECITY_SENTRY_DSN`). Sans DSN, désactivé. Ne transmet aucune
  donnée personnelle (`send_default_pii=False`).
- **Script de restauration** `deploy/restore.sh` (`--latest` ou fichier précis,
  avec confirmation) pour restaurer une sauvegarde PostgreSQL. Documentation
  mise à jour (migrations automatiques + restauration testée).

### Modifié
- L'amorçage (seed) tolère l'absence de tables avant la première migration
  (message clair au lieu d'un plantage).
- Le Dockerfile embarque `migrations/` et `portal/`.

## [3.6.0] — Vérification du téléphone par SMS (OTP)

### Ajouté
- **Vérification obligatoire du numéro de téléphone du citoyen par code SMS**
  pour lutter contre les fausses alertes :
  - À l'inscription, le compte est créé **non vérifié** et un **code à 6
    chiffres** est envoyé par SMS. L'app citoyenne affiche un écran de saisie du
    code (avec « Renvoyer le code »). Endpoints `POST /api/auth/verify-otp` et
    `POST /api/auth/resend-otp`.
  - La **connexion est refusée** tant que le numéro n'est pas vérifié
    (`phone_not_verified`) ; l'app bascule alors automatiquement sur la saisie du
    code. Code à durée de validité limitée + nombre de tentatives borné.
- **Passerelle SMS HTTP générique** (`SAFECITY_SMS_HTTP_*`) compatible avec la
  plupart des agrégateurs locaux (RDC), en plus de Twilio. Repli propre :
  en développement sans passerelle, le code est journalisé côté serveur ; en
  production sans passerelle, message clair (`sms_not_configured`).

### Note de migration
- Le modèle `User` gagne des colonnes (`phone_verified`, champs OTP). En
  développement SQLite, **supprimez `backend/safecity.db`** (recréé
  automatiquement) — les migrations Alembic (itération suivante) rendront ces
  évolutions transparentes.

## [3.5.0] — Sécurité des comptes (vers un usage réel)

### Ajouté
- **Création de compte opérateur contrôlée** : le bouton « Créer un compte » du
  poste opérateur exige désormais un **code d'invitation**
  (`SAFECITY_STAFF_INVITE_CODE`). Si aucun code n'est configuré, l'auto-
  inscription est **désactivée** (403) — sécurité par défaut ; les comptes se
  créent alors via `python -m backend.manage create-admin`. Champ « Code
  d'invitation » ajouté à l'onglet d'inscription.
- **Changement de mot de passe en libre-service** : section « 🔒 Changer mon mot
  de passe » dans les Paramètres du poste opérateur (vérifie le mot de passe
  actuel). Endpoint `POST /api/auth/change-password` (utilisateur connecté).
- **Journal d'audit** : traçabilité des actions sensibles (connexions réussies
  et échouées, création de compte, réinitialisation et changement de mot de
  passe, clôture d'alerte, création/suppression d'agent) avec utilisateur, IP et
  horodatage. Consultation réservée aux administrateurs/superviseurs via
  `GET /api/audit`. Enregistrement *best-effort* (n'interrompt jamais la requête).

### Sécurité
- L'auto-inscription du personnel n'est plus ouverte à tous : un centre de
  surveillance ne peut plus être rejoint sans code d'invitation valide.

## [3.4.1] — Messagerie type WhatsApp (poste opérateur)

### Modifié
- **Messagerie du poste opérateur repensée en bulles façon WhatsApp** : bulles
  **arrondies** ajustées au contenu, avec l'heure — les messages de
  l'**administrateur/opérateur** en **vert à droite**, ceux des **agents** en
  **gris à gauche**. La zone de discussion passe d'un rendu HTML (QTextBrowser)
  à de vrais widgets bulles (QScrollArea + QFrame) pour permettre les coins
  arrondis. Le séparateur « Nouveaux messages » et le marquage non lu sont
  conservés. (Le portail agents affichait déjà ses messages de cette manière.)

## [3.4.0] — Marquage « non lu » par élément (poste opérateur)

### Ajouté
- **Marquage « non lu » de chaque élément** dans le poste opérateur, en plus des
  badges du menu latéral :
  - **Alertes en direct** : une nouvelle alerte non consultée s'affiche **en gras
    avec « ● » et un fond teinté**. Elle devient « lue » quand l'administrateur
    ouvre son incident (double-clic, « Détails » ou acquittement). Le badge du
    menu compte les alertes non lues restantes et diminue au fur et à mesure.
  - **Messagerie** : les messages reçus non lus s'affichent **surlignés (🔵)**
    avec un séparateur « ── Nouveaux messages ── », puis sont marqués lus à
    l'ouverture de la section.
  - **Gestion des agents** : les agents modifiés (disponibilité, ajout/
    suppression) hors de la page sont **surlignés** à l'ouverture, puis marqués lus.
- Compteur de badge piloté par des ensembles d'ids réellement non lus
  (`Sidebar.set_badge`), évitant toute dérive du compteur.

## [3.3.0] — Comptes & mot de passe oublié (poste opérateur)

### Ajouté
- **Écran de connexion du poste opérateur repensé** (onglets) :
  - **« Créer un compte »** : inscription d'un personnel (rôle **opérateur**)
    directement depuis le bureau — nom, e-mail, téléphone (optionnel), mot de
    passe. Connexion automatique après création. Endpoint
    `POST /api/auth/register-staff`.
  - **« Mot de passe oublié ? »** : l'utilisateur saisit son e-mail et reçoit un
    **mot de passe temporaire par e-mail (Gmail)**. Endpoint
    `POST /api/auth/forgot-password` : génère un mot de passe temporaire, l'envoie
    par SMTP puis ne l'enregistre **que si l'envoi réussit** (pas de
    verrouillage de compte). Réponse générique (anti-énumération). Si aucun SMTP
    n'est configuré → message clair `503 email_not_configured`.
- Envoi d'e-mail générique réutilisable (`notifications.send_email_message`,
  `notifications.smtp_configured`) basé sur la configuration `SAFECITY_SMTP_*`
  existante (compatible **Gmail** avec un mot de passe d'application).
- Nouvelle erreur API `503 service_unavailable` (e-mail non configuré / injoignable).
- Tests : inscription opérateur, e-mail déjà utilisé, mot de passe oublié sans
  SMTP (42 tests au total).

## [3.2.1] — Fronts servis par le backend en développement (même origine)

### Ajouté
- En **développement**, le backend sert directement l'**app citoyenne** sur
  `http://localhost:5000/` et le **portail agents** sur
  `http://localhost:5000/portal/` (blueprint `frontend`). Page et API partagent
  ainsi la **même origine** : plus aucun problème de CORS ni de communication
  entre deux serveurs/ports (il suffit de lancer le backend et d'ouvrir
  `http://localhost:5000/`). En production, Nginx continue de servir les fronts
  (ces routes ne sont pas enregistrées).

## [3.2.0] — Comptes citoyens (inscription / connexion)

### Ajouté
- **Compte obligatoire côté app citoyenne** : à la première visite, l'utilisateur
  est invité à **créer un compte** ou à **se connecter** avant d'accéder au bouton
  d'alerte (écran d'authentification à onglets, session mémorisée localement).
- **Inscription** avec **vérification du numéro de téléphone** : si le numéro est
  déjà utilisé, un message clair invite l'utilisateur à se connecter avec ses
  identifiants ou à utiliser un autre numéro. La comparaison ignore le format
  (`+243…`, `243…`, espaces/tirets) pour éviter les doublons. Endpoint
  `POST /api/auth/register` (compte de rôle `citizen`).
- **Connexion par téléphone ou e-mail** : `POST /api/auth/login` accepte un
  identifiant e-mail (personnels) ou numéro de téléphone (citoyens). Compte
  désactivé refusé.
- Les alertes envoyées sont désormais **rattachées au compte** du citoyen
  (`reporter_id`, nom et téléphone pré-remplis).
- Nouvelle erreur API `409 conflict` (numéro/e-mail déjà utilisé).
- 4 tests supplémentaires (inscription, doublon de numéro, validation, connexion).

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
