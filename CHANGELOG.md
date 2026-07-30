# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [1.14.2] — 2026-07-30 — Poste opérateur & portail : position GPS exacte copiable

### Ajouté
- **Poste opérateur** : dans la fenêtre d'incident, la ligne « Position exacte »
  est formatée (ex. « 11.66470°S, 27.47940°E ») et un bouton **« 📋 Copier la
  position GPS »** copie la position dans le presse-papiers (pour la transmettre
  à une patrouille).
- **Portail agents** : la position GPS de chaque alerte est formatée et
  **cliquable** pour la copier (« ✓ copié »).

## [1.14.1] — 2026-07-30 — Site citoyen : coordonnées GPS exactes sous la carte

### Ajouté
- **Position GPS exacte affichée sous la mini-carte** de l'écran de confirmation
  (ex. « 📍 Position exacte : 11.66470°S, 27.47940°E ») — toujours visible, même
  quand le nom du quartier n'est pas encore connu. Un clic **copie** la position
  (pratique pour la transmettre). Libellé traduit FR/SW.

## [1.14.0] — 2026-07-30 — Localisation fiable : vrai quartier + distances correctes

### Corrigé
- **Quartier « Zone XX » factice** remplacé par un **vrai géocodage inverse**
  (OpenStreetMap/Nominatim) : le nom du quartier et l'adresse (rue, commune) sont
  désormais réels. Le géocodage se fait **en arrière-plan**, sans ralentir
  l'alerte, puis met à jour l'incident (le centre voit le quartier apparaître).
  À défaut de réseau côté serveur, on affiche les **coordonnées GPS exactes** —
  jamais un faux quartier.
- **Distance équipe / temps estimé absurdes** (ex. 5 639 km, 13 534 min) :
  - le point de référence par défaut passe de **Kinshasa** à **Lubumbashi** ;
  - la distance est calculée depuis l'**équipe de patrouille la plus proche**
    (positions réelles) et non depuis un point fixe ;
  - les équipes de démonstration sont désormais **à Lubumbashi**.
- L'**adresse d'une alerte contient toujours la position GPS exacte** — c'est le
  localisateur fiable pour la patrouille (avec le marqueur sur la carte et
  l'itinéraire), même sans nom de quartier.

### Ajouté
- Commande `python -m backend.manage relocate-teams` : repositionne vers le
  centre-ville configuré les équipes de patrouille égarées (utile pour un
  déploiement existant dont les équipes de démo étaient restées à Kinshasa).
- Réglages : `SAFECITY_PATROL_LAT/LNG` (centre par défaut) et `SAFECITY_GEOCODING`
  (activer/désactiver le géocodage).

## [1.13.1] — 2026-07-30 — Portail agents : reprise au dernier point de lecture

### Ajouté
- **Reprise au dernier point de lecture** aussi dans la messagerie du **portail
  agents** (comme au poste opérateur). Chaque agent mémorise durablement (par
  agent) l'endroit où il s'était arrêté ; à la réouverture, la vue se positionne
  sur le séparateur **« Nouveaux messages »** et les messages reçus depuis sont
  **surlignés comme non lus**. Conservé même après fermeture/relance (navigateur).

## [1.13.0] — 2026-07-30 — Messagerie : reprise au dernier point de lecture

### Ajouté
- **Reprise automatique au dernier point de lecture** dans la messagerie du poste
  opérateur. Chaque utilisateur mémorise l'endroit exact où il s'était arrêté ;
  à la réouverture de la messagerie, la vue se positionne **sur le séparateur
  « Nouveaux messages »** (et non tout en haut ou tout en bas).
  - Les messages reçus depuis la dernière consultation apparaissent **juste
    après** ce point, clairement identifiés comme **non lus** (surlignés + pastille).
  - Le dernier point de lecture est **enregistré durablement** (par utilisateur),
    donc conservé **même après fermeture et relance** de l'application.
  - Au démarrage, le **badge** du menu Messagerie reflète le nombre de messages
    reçus depuis la dernière lecture.
  - Une fois la messagerie consultée, le point de lecture avance automatiquement
    au dernier message (accusé de lecture ✓✓ inchangé).

## [1.12.4] — 2026-07-30 — Poste opérateur : message clair si dépendances temps réel manquantes

### Corrigé
- **Console inondée** de `requests package is not installed` et de
  `module 'websocket' has no attribute 'WebSocketException'` quand le poste
  n'a pas les bonnes dépendances Python pour le temps réel.
  - L'app **ne tente plus** un transport dont la dépendance manque (polling →
    `requests` ; websocket → `websocket-client`).
  - Si aucun transport n'est utilisable, elle affiche **un seul message clair et
    actionnable** (commandes `pip` à lancer) au lieu de dizaines d'erreurs.
  - L'application reste utilisable : alertes et messages s'actualisent
    automatiquement toutes les 15 s (filet de sécurité REST).
- Note ajoutée dans `desktop/requirements.txt` sur le **conflit** entre le paquet
  `websocket` (incompatible) et `websocket-client` (requis).

## [1.12.3] — 2026-07-30 — Poste opérateur : carte en ligne même en backend local

### Modifié
- **La carte du poste opérateur prend désormais ses tuiles sur le serveur EN
  LIGNE** (production `safecity-lubumbashi.com`, déjà autorisé et connecté à
  Internet), **même quand les données viennent d'un backend local** (`127.0.0.1`).
  Ainsi la carte affiche les vraies rues en local aussi, sans dépendre de l'accès
  Internet de la machine de développement.
  - Un backend local / LAN → tuiles prises en ligne (production).
  - Une connexion à la production réelle → tuiles de ce même serveur.
  - Réglable via la variable `SAFECITY_TILES` (ex. un autre serveur de tuiles).

## [1.12.2] — 2026-07-30 — Proxy de tuiles : repli propre quand le CDN est injoignable

### Corrigé
- **Journal inondé de `502` / `<urlopen error timed out>`** sur le proxy de
  tuiles quand la machine qui exécute le backend **ne peut pas joindre le CDN de
  cartes** (réseau filtré, ou exécution en local derrière le pare-feu). Le proxy :
  - **échoue vite** (délai réduit à 6 s au lieu de 12 s),
  - après quelques échecs, **cesse de solliciter le réseau** pendant 60 s et sert
    directement un **fond neutre** (PNG uni, HTTP 200) au lieu d'une erreur 502 —
    la carte reste lisible (marqueurs/itinéraires) et se réessaie automatiquement,
  - ne **journalise qu'une seule fois** (plus d'inondation du journal).
- Rappel : pour afficher les **rues**, le serveur qui exécute le backend doit
  avoir un accès Internet vers `basemaps.cartocdn.com`. En production (VPS) c'est
  le cas ; en local derrière le pare-feu de la mairie, la carte affiche le fond
  neutre.

## [1.12.1] — 2026-07-27 — Portail agents : médias du citoyen affichés

### Ajouté
- **Photo, vocal et vidéo du citoyen affichés dans le portail agents** (et plus
  seulement au poste opérateur). Sur chaque carte d'alerte : **photo** cliquable
  (ouverture en grand), lecteur **audio** et lecteur **vidéo** intégrés, ainsi
  que la **description** du signalement. Les agents sur le terrain disposent
  ainsi de tout le contexte média.

## [1.12.0] — 2026-07-27 — Le citoyen peut joindre une vidéo à son alerte

### Ajouté
- **Envoi de vidéo depuis le site citoyen** : en plus de la photo et du vocal, le
  citoyen peut désormais **joindre une vidéo** à son alerte (bouton 🎬 Vidéo,
  fichier ou capture caméra), avec aperçu avant envoi. Limite ~18 Mo côté client
  (pour rester sous la taille de requête autorisée) et message si trop lourd.
  Bouton traduit **FR/SW** (Vidéo / Video).
- **Poste opérateur** : bouton **« 🎬 Voir la vidéo du citoyen »** dans la fenêtre
  d'incident (lecteur intégré QVideoWidget + repli lecteur système).
- Backend : colonne `video_path` sur `alerts` (migration `c6e0a2b48d19`),
  validation et sauvegarde de la vidéo, `video_url` renvoyé par l'API.

## [1.11.0] — 2026-07-27 — Poste opérateur : écouter le vocal du citoyen + photo en grand

### Corrigé / Ajouté
- **Message vocal joint par le citoyen désormais écoutable** sur le poste
  opérateur. Le citoyen pouvait joindre un vocal à son alerte et le backend le
  stockait bien (`audio_url`), mais la fenêtre d'incident n'offrait **aucun moyen
  de l'écouter**. Ajout d'un bouton **« 🎧 Écouter le message vocal du citoyen »**
  (lecture/arrêt, gestion d'erreur réseau/format).
- **Photo du citoyen agrandissable** : la miniature de la fenêtre d'incident est
  maintenant **cliquable** pour afficher la photo en grand.

## [1.10.1] — 2026-07-27 — Langue : démarrage toujours en Français

### Modifié
- L'application citoyenne **démarre toujours en Français** à chaque ouverture.
  Le choix de langue n'est plus mémorisé entre les visites (il l'était par
  origine, ce qui pouvait afficher le Swahili « tout seul » sur une origine où il
  avait été activé). Le bouton **FR/SW** reste disponible pour basculer pendant
  la visite ; un rechargement repart en Français.

## [1.10.0] — 2026-07-26 — Application citoyenne bilingue (Français / Swahili)

### Ajouté
- **Version Swahili** de l'application citoyenne (Lubumbashi étant largement
  swahiliphone) : un **bouton de langue** dans l'en-tête bascule l'interface
  entre **Français** et **Kiswahili** d'un clic, et le choix est **mémorisé**.
  - Tous les écrans citoyens sont traduits : connexion/inscription, bouton
    d'alerte, types de danger (Wizi, Unyang'anyi, Moto, Ajali, Vurugu…), détails
    de l'incident, avertissement légal, confirmation, et **suivi d'alerte**
    (chronologie et messages d'avancement).
  - Système d'i18n léger (`web/js/i18n.js`, attributs `data-i18n`) sans
    dépendance externe ; repli automatique sur le Français.

## [1.9.0] — 2026-07-26 — Regroupement des signalements en doublon

### Ajouté
- **Regroupement automatique des doublons** : quand plusieurs citoyens signalent
  le **même incident** (même type, à proximité et dans une courte fenêtre de
  temps), les signalements sont **regroupés** sous un incident principal — pour
  éviter d'envoyer plusieurs patrouilles au même endroit.
  - Seuils configurables : `SAFECITY_DEDUP_RADIUS_M` (défaut 150 m),
    `SAFECITY_DEDUP_WINDOW_MIN` (défaut 10 min), `SAFECITY_DEDUP` pour
    activer/désactiver.
  - Un doublon **ne crée pas** de nouvel incident à l'écran (pas de pop-up ni
    d'alarme redondante) : le **compteur de signalements liés** du principal
    s'incrémente en temps réel (`alert_updated`).
  - **Poste opérateur** : bandeau « 🔁 N signalements du même incident » dans la
    fenêtre d'incident + marqueur « 🔁N » dans la liste des alertes.
  - **Portail agents** : ligne et marqueur « 🔁 N signalements regroupés » sur la
    carte d'alerte.
  - **Suivi citoyen** : chaque citoyen garde **sa** référence, mais un doublon
    suit l'avancement de l'**incident principal** (celui qui est réellement
    traité) — statut et agent affecté cohérents pour tout le monde.
- Migration `b4d8f1a3c705` : colonne `duplicate_of_id` (auto-référence) sur
  `alerts`. La liste opérateur n'affiche que les incidents principaux.

## [1.8.0] — 2026-07-26 — Suivi d'alerte pour le citoyen

### Ajouté
- **Suivi d'alerte côté citoyen** : chaque alerte reçoit une **référence
  publique** lisible (ex. « SC-K7P2Q9 »). Le citoyen voit l'**avancement en
  direct** de son signalement — *Alerte reçue → Prise en charge → Résolue* —
  avec l'horodatage de chaque étape et le **prénom de l'agent** affecté.
  - Sur l'écran de confirmation : référence mise en avant + chronologie qui se
    **rafraîchit automatiquement** (toutes les 15 s, repli si le temps réel est
    bloqué) jusqu'à la clôture, avec un message contextuel (« Un agent a été
    affecté… », « Votre alerte a été traitée et clôturée »).
  - Nouvel écran **« Suivre une alerte »** : le citoyen peut revenir plus tard
    et retrouver l'état de son alerte en saisissant sa référence.
  - Endpoint public `GET /api/alerts/track/<référence>` renvoyant uniquement
    l'avancement — **aucune donnée sensible** (ni nom/téléphone du déclarant, ni
    description, ni GPS exact), et référence non énumérable.
- Migration `a2c4e6f80b13` : colonne `public_ref` (indexée, unique) sur `alerts`.

## [1.7.6] — 2026-07-26 — Temps réel : connexion WebSocket (résout « Hors ligne »)

### Corrigé
- **Poste opérateur bloqué sur « Hors ligne »** (le temps réel ne se connectait
  pas depuis le réseau de la mairie). Le client était **verrouillé sur le
  long-polling** (héritage de l'ancien serveur Waitress). Or les pare-feu
  filtrants — comme celui de la mairie, qui bloque déjà les CDN externes —
  coupent souvent le long-polling (requêtes HTTP maintenues ouvertes ~25 s) tout
  en laissant passer les **WebSockets** (une seule connexion « upgradée »).
  - Le poste opérateur tente désormais **WebSocket d'abord, puis se rabat sur le
    long-polling**. Le serveur de production (gunicorn/eventlet) et Nginx gèrent
    déjà les deux ; en dev sous Waitress, la tentative WebSocket échoue proprement
    et le polling prend le relais.
  - Ordre personnalisable via `SAFECITY_SOCKET_TRANSPORTS`
    (ex. `"polling,websocket"`).
  - `websocket-client` épinglé dans les dépendances du poste opérateur pour
    garantir la disponibilité du transport WebSocket.

### Vérifié
- Chaîne complète reproduite localement (**gunicorn/eventlet derrière Nginx** avec
  le `proxy.conf` de production) : **polling ET WebSocket se connectent** et
  reçoivent les événements — la configuration Nginx `/socket.io/` est correcte.
  Le blocage venait bien de la restriction au polling côté client, pas du serveur
  ni du proxy.

## [1.7.5] — 2026-07-26 — Badge « messages non lus » fiable même hors ligne

### Corrigé
- **Badge « messages non lus » qui n'apparaissait plus** sur le poste opérateur.
  Il ne dépendait que du **temps réel** (`chat_message`) : si le socket est hors
  ligne (réseau de la mairie), aucun message ne remontait et le badge ne
  s'affichait jamais.
  - Le filet de sécurité périodique (15 s) détecte désormais les **nouveaux
    messages par REST** et met à jour le **badge du menu Messagerie**, avec son
    de notification et toast — même socket hors ligne.
  - Aucune double notification : les ids de messages vus sont partagés entre le
    chemin temps réel et le chemin REST (`_known_msg_ids`). Ses propres messages
    n'incrémentent pas le badge ; sur la page Messagerie ouverte, les nouveaux
    messages sont chargés directement (accusé de lecture, pas de badge).

## [1.7.4] — 2026-07-26 — Gestion des citoyens : état vide clair + diagnostic

### Corrigé
- **Page « Gestion des citoyens » qui semblait vide/cassée** : le tableau
  n'affichait aucun retour quand aucun citoyen n'est inscrit (juste un fond
  vide). Ajout d'un **message d'état vide explicite** (« Aucun citoyen inscrit
  pour le moment. ») et d'un **compteur** en en-tête (« N citoyen(s)
  inscrit(s) »), pour distinguer « aucune donnée » d'un vrai bug.
  - L'endpoint `/api/citizens` et le flux d'inscription ont été **vérifiés de
    bout en bout** (un citoyen inscrit a bien le rôle `citizen` et apparaît dans
    la liste renvoyée à l'opérateur). Le vide venait de l'absence de citoyens
    dans la base, pas d'un défaut d'affichage.

### Ajouté
- Commande d'administration **`list-citizens`** (`python -m backend.manage
  list-citizens`) : liste les comptes citoyens inscrits (nom, téléphone,
  e-mail, date) — utile pour vérifier côté serveur combien de citoyens existent.

## [1.7.3] — 2026-07-26 — Poste opérateur : alertes en direct fiabilisées

### Corrigé
- **Nouvelle alerte citoyenne qui n'apparaissait pas** sur le poste opérateur
  sans redémarrer l'application. Le rafraîchissement périodique de sécurité
  (toutes les 15 s) ne rechargeait que les **compteurs** de statistiques, pas la
  **liste des alertes** : si un événement temps réel `new_alert` était manqué
  (coupure réseau, socket tombée sur le réseau de la mairie), l'alerte restait
  invisible jusqu'au prochain démarrage.
  - Le filet de sécurité recharge désormais les alertes par **REST** et intègre
    celles qu'un événement temps réel aurait pu manquer — l'alerte apparaît en
    quelques secondes, **sans redémarrage**.
  - Les alertes ainsi rattrapées sont **notifiées** (son + badge « non lu » +
    toast) sans ouvrir un pop-up d'incident par alerte (pas de submersion).
  - En cas de panne réseau, le rechargement est simplement retenté au tick
    suivant.
- Émission temps réel `new_alert` **vérifiée de bout en bout** (serveur eventlet
  de production + client Socket.IO en long-polling) : le backend diffuse bien
  l'alerte ; le correctif porte sur la robustesse côté poste opérateur.

## [1.7.2] — 2026-07-26 — Tuiles de carte servies par le serveur (proxy)

### Corrigé
- **Carte qui restait blanche** malgré le fond CARTO : le **pare-feu de la mairie
  bloque tous les CDN de tuiles externes** (OpenStreetMap comme CARTO). Les
  clients ne pouvaient donc jamais télécharger le fond de carte.

### Ajouté
- **Proxy de tuiles côté serveur** (`GET /tiles/<z>/<x>/<y>.png`) : c'est le
  serveur SafeCity qui récupère les tuiles CARTO Voyager (fond coloré, style
  OpenStreetMap) et les **met en cache sur disque**, puis les sert depuis son
  propre domaine — déjà autorisé par le pare-feu. Les clients ne contactent plus
  que `safecity-lubumbashi.com`.
  - **Poste opérateur** : `map.html` bascule le fond vers `<serveur>/tiles/…`
    via `window.setTileServer()`, alimenté par l'URL du serveur (`MapPage`).
  - **Portail agents** et **site citoyen** : fond pointant vers
    `<API_BASE>/tiles/…`.
  - **Nginx** : `location /tiles/` proxifié vers le backend (cache 30 jours).

## [1.7.1] — 2026-07-26 — Fond de carte fiable (CARTO Voyager)

### Corrigé
- **Carte qui restait blanche** (« Fond de carte hors-ligne ») : le serveur public
  `tile.openstreetmap.org` bloquait/limitait le chargement des tuiles sur certains
  réseaux. Remplacé par **CARTO Voyager** — un fond **coloré** (style
  OpenStreetMap) servi par le CDN CARTO, plus fiable. Appliqué au **poste
  opérateur**, au **portail agents** et au **site citoyen**.

## [1.7.0] — 2026-07-25 — Inscription citoyenne directe (sans code de vérification)

### Modifié
- **Suppression de la vérification par code (OTP)** à l'inscription citoyenne :
  le compte est **activé immédiatement** dès que le formulaire est rempli, et le
  citoyen est **connecté directement** (jeton renvoyé par `/register`).
- **E-mail redevenu optionnel** (il servait uniquement à recevoir le code) —
  utile désormais surtout pour la récupération de mot de passe. `/api/meta`
  renvoie `email_required: false`.
- La **connexion** ne bloque plus sur « numéro non vérifié ».
- L'unicité du **numéro de téléphone** reste vérifiée. Les endpoints de code
  (verify/resend) subsistent mais ne sont plus utilisés par l'inscription.

## [1.6.1] — 2026-07-25 — Message de vérification e-mail plus clair

### Modifié
- **Formulation e-mail-first** : le message affiché au citoyen ne mentionne plus
  « Le SMS étant indisponible » (perçu comme un secours). Il indique simplement
  « Un code de vérification à 6 chiffres a été envoyé à votre adresse e-mail »
  (réponse API + écran de saisie du code). Cohérent avec un déploiement où
  l'e-mail est la méthode principale.

## [1.6.0] — 2026-07-25 — Onglet « Infos » : présence & lecture par participant

### Ajouté
- **Onglet/bouton « ℹ️ Infos »** dans la messagerie (poste opérateur et portail
  agents) : liste des participants avec **présence en ligne** (🟢/⚪) et **statut
  de lecture** du dernier message (✓✓ a vu / … pas encore) — pour repérer ceux
  qui sont connectés mais n'ont pas vu les messages. Mise à jour **en temps réel**.
- **Présence par utilisateur** : chaque client s'identifie après connexion
  (événement `identify`) ; le serveur diffuse un événement `presence`. Nouvel
  endpoint `GET /api/messages/participants`.

## [1.5.0] — 2026-07-25 — Accusés de lecture (✓✓) dans la messagerie

### Ajouté
- **Accusés de lecture façon WhatsApp** : les messages envoyés affichent **✓**
  (envoyé) puis **✓✓** (bleu, lu) dès qu'un autre participant a ouvert la
  messagerie après l'envoi. Sur le **poste opérateur** et le **portail agents**,
  mise à jour **en temps réel** (événement Socket.IO `messages_read`).
- **Backend** : suivi de lecture par `users.messages_seen_at` (**migration**
  `e7a1c9d4f2b6`), champ `read` par message dans `GET /api/messages`, endpoint
  `POST /api/messages/read`, diffusion de l'accusé aux participants.
  L'ouverture de la messagerie marque automatiquement la lecture.

## [1.4.0] — 2026-07-25 — Vidéos dans la messagerie (façon WhatsApp)

### Ajouté
- **Envoi et lecture de vidéos** dans la messagerie opérateurs ↔ agents :
  - **Poste opérateur** : bouton 🎥 (choix d'un fichier), lecture dans une
    fenêtre intégrée (QVideoWidget) avec repli sur le lecteur système.
  - **Portail agents** : bouton 🎥 et lecture en ligne (`<video controls>`).
  - **Backend** : champ `video` accepté (formats `mp4/webm/ogg/mov/m4v`),
    exposé via `video_url`. Nouvelle colonne `messages.video_path` +
    **migration Alembic** `d5f9a3c1e8b2`.
- Limite de taille : **20 Mo** par vidéo (courtes séquences) ; `MAX_UPLOAD_MB`
  par défaut porté à **32 Mo** pour la marge d'encodage base64.

## [1.3.9] — 2026-07-25 — Correctifs médias messagerie (poste opérateur)

### Corrigé
- **Photo en pièce jointe affichée en ligne** (miniature dans la bulle) et
  **agrandissable au clic**, au lieu d'un lien qui ne s'ouvrait pas.
- **Lecture d'un message vocal débloquée** : clic pour lire, nouveau clic pour
  **arrêter** (plus de blocage), passage propre d'un vocal à l'autre, gestion
  des erreurs de lecture.
- **Enregistrement vocal muet** : périphérique d'entrée par défaut explicite,
  **volume au maximum + micro démuté**, encodage haute qualité (corrige les
  vocaux silencieux sous Windows). *(À confirmer sur votre poste.)*

## [1.3.8] — 2026-07-25 — Nom d'expéditeur des e-mails

### Ajouté
- **Nom d'expéditeur** dans les e-mails : les destinataires voient désormais
  « **SafeCity Lubumbashi** <adresse> » au lieu de l'adresse seule. Configurable
  via `SAFECITY_SMTP_FROM_NAME` (défaut : « SafeCity Lubumbashi »). S'applique à
  tous les envois (codes de vérification, mot de passe oublié, alertes).

## [1.3.7] — 2026-07-25 — Carte claire : OpenStreetMap standard (coloré) partout

### Modifié
- **Fond de carte clair** au lieu du fond sombre, sur les **trois** interfaces
  (**poste opérateur**, **portail agents**, **site citoyen**). Tuiles **standard
  OpenStreetMap** (colorées). Fonds des conteneurs passés en clair aussi
  (chargement / hors-ligne). Marqueurs et légendes inchangés.

## [1.3.6] — 2026-07-25 — Fenêtre de connexion sans identifiants de démo

### Modifié
- **Retrait du pré-remplissage de démonstration** (`operateur@safecity.local` /
  `safecity123`) sur la fenêtre de connexion du poste opérateur : champs vides
  avec indications (« votre e-mail » / « votre mot de passe ») et note adaptée.
  Évite la confusion en production, où le compte de démo a été supprimé.

## [1.3.5] — 2026-07-25 — Serveur choisissable dès la fenêtre de connexion

### Ajouté
- **Champ « Serveur » dans la fenêtre de connexion** du poste opérateur :
  pré-rempli avec l'adresse courante, il permet de choisir le serveur **avant**
  de se connecter. La valeur est appliquée à la connexion / création de compte
  et **mémorisée** (comme dans Paramètres › Serveur).

## [1.3.4] — 2026-07-25 — Serveur configurable dans les Paramètres (poste opérateur)

### Ajouté
- **Champ « Serveur » modifiable** dans Paramètres du poste opérateur : l'adresse
  du serveur (API + temps réel) est éditable et **mémorisée** (QSettings). Prise
  en compte au prochain démarrage.
- **Serveur par défaut = production** `https://safecity-lubumbashi.com`. Priorité :
  variable `SAFECITY_API` (explicite) > adresse enregistrée dans les Paramètres >
  ce défaut. Pour le développement local : `SAFECITY_API=http://localhost:5000`.

## [1.3.3] — 2026-07-25 — Bouton « Actualiser » (poste opérateur)

### Ajouté
- **Bouton « 🔄 Actualiser »** dans la barre du haut du poste opérateur : recharge
  à la demande les alertes, statistiques, agents et messages (équivalent visible
  du raccourci **F5**). Retour visuel pendant l'actualisation (« ⏳ Actualisation… »)
  puis notification « Données actualisées ».

## [1.3.2] — 2026-07-25 — Correctif : messages temps réel du poste opérateur

### Corrigé
- **Les messages n'apparaissaient qu'après un redémarrage** de l'application
  bureau. Le client Socket.IO n'écoutait que `new_alert`/`alert_updated` : les
  événements **`chat_message`, `agent_updated`, `agent_deleted`, `agents_count`**
  n'étaient jamais reçus. Ils sont désormais tous enregistrés → messages,
  mises à jour et suppressions d'agents s'affichent **en direct**.

## [1.3.1] — 2026-07-25 — Correctif : messages vocaux du poste opérateur (Windows)

### Corrigé
- **Envoi d'un message vocal depuis le poste opérateur** échouait avec
  « Type de fichier non autorisé pour audio : .mp4 ». Sous Windows, QtMultimedia
  produit un conteneur **MP4/AAC** annoncé `audio/mp4` (identique à `.m4a`). Le
  backend normalise désormais `audio/mp4` (et `x-m4a`, `aac`) en **`.m4a`**, qui
  est un format audio accepté et lisible côté web comme bureau.

## [1.3.0] — 2026-07-25 — Sous-domaine dédié pour le portail agents

### Ajouté
- **Portail agents sur un sous-domaine dédié** (ex. `agents.<domaine>`), en plus
  de l'accès `/<domaine>/portal/` conservé pour compatibilité. Configuration via
  `SAFECITY_PORTAL_DOMAIN` ; le certificat Let's Encrypt couvre les deux noms
  (SAN) et l'API/temps réel/uploads sont proxifiés sur les deux domaines.
- Nginx : locations communes factorisées dans `deploy/nginx/proxy.conf` (incluses
  par chaque bloc `server`).
- `deploy/install.sh` demande le sous-domaine (défaut `agents.<domaine>`) et
  renseigne les **deux origines CORS** ; `init-letsencrypt.sh` émet un certificat
  multi-domaines ; checklist mise à jour (DNS des deux noms + procédure d'ajout
  du sous-domaine à un déploiement existant).

## [1.2.2] — 2026-07-24 — E-mail obligatoire à l'inscription sans SMS

### Modifié
- **E-mail requis à l'inscription citoyenne tant qu'aucune passerelle SMS n'est
  configurée** : c'est alors le seul canal pour transmettre le code de
  vérification, donc l'inscription l'exige (message clair, champ `email`).
  Dès qu'un SMS est configuré, l'e-mail redevient optionnel.
- `/api/meta` expose `email_required` ; le formulaire citoyen **adapte
  automatiquement** le libellé (« requis »), rend le champ obligatoire et valide
  côté client.
- Ordre de validation : le **consentement** est vérifié avant la règle e-mail.

## [1.2.1] — 2026-07-24 — Configuration e-mail Gmail (envoi des codes aux citoyens)

### Ajouté
- **Commande `python -m backend.manage test-email --to <adresse>`** : envoie un
  e-mail de test pour vérifier la configuration SMTP/Gmail avant la mise en
  service (message d'aide clair si le SMTP n'est pas configuré ou si Gmail refuse
  le mot de passe).
- **`.env.example`** : bloc **Gmail prêt à l'emploi** (smtp.gmail.com + étapes du
  « mot de passe d'application ») pour que les citoyens reçoivent leurs codes de
  vérification par e-mail.

### Sécurité / qualité
- **`deploy/.env.prod` et `.env.*` ajoutés au `.gitignore`** : les fichiers de
  secrets de production ne peuvent plus être commités par erreur.
- **Tests hermétiques** : la configuration de test ignore désormais toute
  passerelle e-mail/SMS d'un `.env` local (les tests ne dépendent plus de la
  machine).

## [1.2.0] — 2026-07-24 — Passerelle SMS RDC (Orange) & repli e-mail pour l'OTP

### Modifié
- **Twilio retiré** (coûteux et couverture RDC limitée). La passerelle SMS
  sélectionne désormais, par priorité : **Orange RD Congo** (API officielle de
  l'opérateur, recommandée), **passerelle HTTP générique** (tout agrégateur/
  opérateur local), puis **Africa's Talking** (régional).
- Les **alertes par SMS** aux superviseurs passent par cette passerelle unifiée
  (`SAFECITY_SMS_ALERT_TO`) au lieu de Twilio.

### Ajouté
- **Connecteur Orange SMS** (OAuth2 `client_credentials` + envoi), configurable
  via `SAFECITY_ORANGE_CLIENT_ID` / `_CLIENT_SECRET` / `_SENDER`.
- **Repli e-mail pour la vérification (OTP)** : si le SMS est indisponible ou
  échoue et que le citoyen a fourni un e-mail (SMTP configuré), le code de
  vérification est envoyé **par e-mail** — l'inscription continue de fonctionner
  même en cas de panne SMS. Le canal utilisé (`sms` / `email` / `dev`) est
  renvoyé par l'API et **affiché au citoyen** (texte adapté sur l'écran de code).
- Champ e-mail d'inscription marqué **« optionnel, recommandé »** avec une note
  expliquant son rôle de secours.

### Vérifié
- 54 tests (dont repli e-mail et détection de passerelle) ; suppression de
  Twilio confirmée dans toute la configuration.

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
