# Checklist de test — Poste opérateur (application bureau)

Objectif : vérifier, sur une vraie machine, que l'application bureau fonctionne
de bout en bout — en particulier les **messages vocaux** et les dernières
améliorations (tableau de bord, séparateurs de date, bulles de messagerie).

> Cochez chaque case. En cas d'échec, notez le comportement observé à côté de la
> ligne concernée.

---

## 0. Prérequis

- [ ] **Micro branché et fonctionnel** sur la machine du poste opérateur
      (indispensable pour l'enregistrement vocal). Testez-le dans un autre logiciel
      si vous avez un doute.
- [ ] **Backend démarré** et joignable (base de données à jour, cf. §1).
- [ ] Python + dépendances installées (`pip install -r requirements.txt`), y
      compris **PySide6** avec le module multimédia.

---

## 1. Mettre à jour la base de données (migration du vocal)

La colonne `messages.voice_path` a été ajoutée : il faut appliquer la migration.

- [ ] **En développement (SQLite)** : rien à faire, la table est créée
      automatiquement au démarrage.
- [ ] **En production / PostgreSQL** : appliquer les migrations
  - Sans Docker : `flask db upgrade`
  - Avec Docker :
    `docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml exec backend flask db upgrade`
- [ ] Vérifier qu'aucune erreur n'apparaît et que la migration `b3d7e1f2a9c4`
      (*add voice_path to messages*) est bien appliquée.

---

## 2. Démarrer les composants

- [ ] **Backend** (dans un terminal) :
      `python -m backend.app` → doit afficher un démarrage sur
      `http://localhost:5000`.
- [ ] **Poste opérateur** (dans un autre terminal) :
      `python -m desktop.main`
      *(si le backend n'est pas en local : `SAFECITY_API=https://<domaine> python -m desktop.main`)*
- [ ] **Portail agents** (pour simuler un agent qui envoie un vocal) :
      ouvrir `http://localhost:5000/portal/` dans un navigateur
      *(en dev via `python -m backend.app`)*, **en HTTPS ou sur localhost**
      (le micro du navigateur exige un contexte sécurisé).

Comptes de démonstration (si `SAFECITY_SEED_DEMO=true`) — mot de passe
`safecity123` pour tous :

| Rôle | Identifiant |
|------|-------------|
| Opérateur (bureau) | `operateur@safecity.local` |
| Agent (portail) | `agent1@safecity.local` |

---

## 3. Connexion & interface générale

- [ ] La fenêtre de **connexion** s'ouvre ; l'icône bouclier apparaît dans la barre
      des tâches.
- [ ] Le bouton **œil** affiche/masque le mot de passe ; le bouton de connexion
      passe en état « chargement » pendant l'authentification.
- [ ] Après connexion, la **barre d'état** (bas de fenêtre) montre : connecté,
      compteurs, heure de mise à jour.

---

## 4. Tableau de bord (peaufinage récent)

- [ ] En haut : **salutation** correcte selon l'heure (Bonjour / Bon après-midi /
      Bonsoir) et **date du jour** en français.
- [ ] **Pastille de situation** à droite : 🟢 « Situation calme » sans alerte en
      cours, sinon 🟠 / 🔴 avec le nombre d'alertes actives.
- [ ] Les **4 tuiles** affichent des chiffres cohérents et un **sous-titre**
      contextuel (ex. « X% des cas traités »).
- [ ] **Clic sur une tuile** « Alertes … » → ouvre *Alertes en direct* ; clic sur
      « Agents connectés » → ouvre *Gestion des agents* (curseur main au survol).

---

## 5. Messagerie — séparateurs de date & bulles

- [ ] Ouvrir la **Messagerie** : les messages sont regroupés par jour avec une
      **pastille de date** centrée (*Aujourd'hui*, *Hier*, jour de la semaine, ou
      date complète).
- [ ] Les **bulles** sont bien positionnées : **mes messages à droite** (vert),
      **ceux des agents à gauche** (gris), avec **l'heure** sous chaque message.

---

## 6. Messages vocaux — ENVOI depuis le bureau

- [ ] Le bouton **🎤** est **visible** à côté du trombone 📎.
      *(S'il est absent : aucun micro détecté — vérifiez le §0.)*
- [ ] Cliquer sur **🎤** : le bouton passe en **⏹ (rouge)** et un indicateur
      « 🔴 Enregistrement… m:ss » s'affiche avec un **minuteur** qui avance.
- [ ] Parler quelques secondes, puis cliquer **⏹** pour arrêter.
- [ ] Le message **« 🎤 Message vocal prêt — cliquez sur Envoyer »** apparaît.
- [ ] Cliquer **Envoyer** : une bulle **« ▶ Message vocal »** apparaît **à droite**
      (côté « Moi »).
- [ ] Cliquer sur **▶ Message vocal** : le son enregistré se lit (le bouton passe à
      **⏸**, puis revient à ▶ à la fin).
- [ ] **Limite de durée** : laisser tourner un enregistrement > 2 min → il s'arrête
      automatiquement.
- [ ] **Envoi vocal + texte** : enregistrer un vocal, taper aussi du texte, puis
      Envoyer → la bulle contient le texte **et** le lecteur vocal.

---

## 7. Messages vocaux — RÉCEPTION d'un vocal d'agent

- [ ] Sur le **portail agents** (connecté en `agent1@safecity.local`), ouvrir la
      messagerie, cliquer **🎤**, enregistrer, écouter la pré-écoute, puis
      **Envoyer**.
- [ ] Sur le **poste opérateur**, le vocal de l'agent arrive **en temps réel** :
  - [ ] une bulle **« ▶ Message vocal » à gauche** (côté agent) ;
  - [ ] un **son de notification** se joue (si le son n'est pas coupé) ;
  - [ ] si l'on n'est **pas** sur la page Messagerie : **badge « non lu »** sur le
        menu + mise en évidence à l'ouverture.
- [ ] Cliquer **▶ Message vocal** sur le poste opérateur → le vocal de l'agent se
      **lit correctement**.
- [ ] Inversement, le vocal envoyé par le bureau (§6) est **audible sur le portail
      agents** (lecteur `<audio>`).

---

## 8. Cas limites & robustesse

- [ ] **Sans micro** (débrancher / machine sans entrée audio) : le bouton 🎤 est
      **masqué**, le reste de la messagerie fonctionne normalement (texte + image).
- [ ] **Annuler un enregistrement** en cours puis en démarrer un autre : pas de
      blocage, le dernier enregistrement est bien celui envoyé.
- [ ] **Message vide** : sans texte, sans image, sans vocal → le bouton Envoyer ne
      crée rien (aucune bulle vide).
- [ ] **Reconnexion** : couper puis relancer le backend → le poste se reconnecte et
      les nouveaux vocaux passent toujours.

---

## 9. Résultat

- [ ] Tous les points ci-dessus sont **au vert** → la fonctionnalité vocale est
      validée sur le poste opérateur.
- [ ] Sinon, lister ici les lignes en échec et le comportement observé :

```
(notes de test)
```
