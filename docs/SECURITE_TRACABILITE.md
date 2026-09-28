# SafeCity Lubumbashi — Sécurité, traçabilité et gouvernance

Document de présentation officielle (Mairie de Lubumbashi). Il décrit les
mécanismes **réellement en place** dans la version 1.23 et où les montrer dans
l'application.

> À montrer en direct : poste opérateur → menu **🔐 Sécurité & traçabilité**,
> puis la fiche d'un incident → **📜 Journal de l'intervention** et
> **🚫 Fausse alerte**.

---

## 1. Authentification

| Mécanisme | Détail |
|---|---|
| Comptes nominatifs | Chaque opérateur, agent, superviseur a **son propre compte** (e-mail + mot de passe). Aucun compte partagé : chaque action est attribuable à une personne. |
| Mots de passe | Hachés avec **bcrypt** (sel unique). Le mot de passe n'est jamais stocké ni lisible, même par l'administrateur. |
| Session | Jeton **JWT signé** (HS256), expiration après **12 h** (paramétrable). |
| Anti-force brute | **8 essais / 5 min** par adresse, puis blocage temporaire. Chaque échec est journalisé. |
| Citoyens | Vérification du téléphone par **code SMS** (6 chiffres, 10 min, 5 essais). |
| Comptes désactivés | Accès refusé immédiatement (tentative journalisée). |
| Création de comptes personnel | Soumise à un **code d'invitation** ; sinon par l'administrateur uniquement. |

## 2. Rôles et responsabilités (gouvernance)

| Rôle | Peut | Responsabilité |
|---|---|---|
| **Citoyen** | Déclencher une alerte (type, GPS, photo, vocal, vidéo), suivre **son** dossier par référence | Signaler de bonne foi |
| **Agent** | Voir ses interventions, partager sa position, accepter / terminer une intervention | Intervenir sur le terrain, tenir son statut à jour |
| **Opérateur** | Qualifier les alertes, affecter agent / patrouille, suivre le trajet, clôturer, **classer en fausse alerte** (motif obligatoire), rapports | Traiter chaque alerte jusqu'à sa clôture |
| **Superviseur** | Tout ce que fait l'opérateur + **journal d'audit complet**, **annuler une fausse alerte**, gérer les agents | Contrôler l'activité du centre |
| **Administrateur** | Tout + comptes, paramètres, conservation des données | Administrer la plateforme |

**Séparation des tâches** : l'opérateur ne consulte pas le journal d'audit
global (il ne contrôle pas ses propres actions) et ne peut pas annuler une
fausse alerte : c'est le superviseur qui contrôle.

Les droits sont vérifiés **côté serveur** à chaque requête (un poste modifié ne
peut pas les contourner).

## 3. Historique des actions (journal d'audit)

Chaque action sensible est enregistrée avec : **date/heure, utilisateur, rôle,
action, détail, adresse IP, incident concerné**.

Actions tracées : connexion, échec de connexion, compte désactivé, mot de passe
modifié / réinitialisé, création / suppression de comptes et d'agents, alerte
reçue, signalement regroupé, patrouille envoyée, agent affecté, intervention
acceptée / terminée, incident clôturé, fausse alerte signalée / annulée, export
de données (CSV / Excel), rapport PDF généré.

Consultation : menu **🔐 Sécurité & traçabilité → Historique des actions**
(superviseur / administrateur), avec recherche.

## 4. Journal des interventions

Chaque incident (ex. **SC-2026-0048**) a sa chronologie :

```
28/09/2026 13:48:02  Alerte reçue                     Jean M.      Citoyen
28/09/2026 13:48:40  Agent affecté                    Opérateur A. Opérateur  Patrick → SC-2026-0048
28/09/2026 13:49:05  Intervention acceptée par l'agent Patrick     Agent
28/09/2026 14:02:31  Intervention terminée par l'agent Patrick     Agent
```

Accès : fiche de l'incident → **📜 Journal de l'intervention** (aussi depuis
les alertes en direct et l'historique). Copiable pour un rapport.

## 5. Fausses alertes

- Tout opérateur peut classer une alerte en **fausse alerte**, avec un **motif
  obligatoire** (canular, erreur de manipulation, aucun incident constaté,
  doublon, test, autre + précision).
- L'alerte est clôturée, l'agent et la patrouille sont libérés.
- Auteur, heure et motif sont inscrits au journal de l'intervention.
- **Annulation réservée au superviseur / administrateur**, raison obligatoire.
- **Aucun blocage automatique du citoyen** : une vraie urgence reste possible.
  Ses alertes suivantes affichent un avertissement « ce citoyen a déjà N
  fausses alertes » ; l'opérateur reste décideur.
- Le citoyen voit « Classée sans suite (fausse alerte) » dans son suivi, sans
  le motif interne ni le nom de l'opérateur.
- Indicateurs : nombre et taux de fausses alertes sur 30 jours, citoyens
  récidivistes (téléphone masqué).

## 6. Protection des données

- Nom, téléphone et position GPS des citoyens : **réservés au personnel
  authentifié** (API et flux temps réel).
- Suivi citoyen par **référence aléatoire** (non devinable), sans aucune donnée
  personnelle.
- Photos, vocaux, vidéos : servis uniquement par **liens signés** à durée
  limitée (24 h) ; un lien sans signature est refusé.
- Transport chiffré **HTTPS** (TLS Let's Encrypt) en production.
- **Consentement** à la politique de confidentialité enregistré à l'inscription.
- **Conservation limitée** (365 jours par défaut) puis purge ; le citoyen peut
  supprimer son compte (ses alertes sont anonymisées).
- En-têtes de sécurité HTTP, CORS restreint en production, clé secrète
  obligatoire en production.

## 7. Résilience et continuité

- **Sauvegarde automatique** PostgreSQL (toutes les 24 h, 14 copies conservées),
  restauration scriptée (`deploy/restore.sh`).
- Côté citoyen : si le réseau tombe, l'alerte est **mise en file** sur le
  téléphone et renvoyée automatiquement.
- Poste opérateur : rafraîchissement périodique si le temps réel est coupé ;
  indicateur « En ligne / Hors ligne ».
- Regroupement des doublons : plusieurs signalements du même incident = une
  seule intervention.
- Sonde de santé `/api/health` pour la supervision ; journaux applicatifs.

## 8. Recommandations d'exploitation

1. Créer un vrai compte administrateur puis **désactiver les comptes de
   démonstration** (`SAFECITY_SEED_DEMO=false`).
2. Un compte par personne ; désactiver immédiatement le compte d'un agent qui
   quitte le service.
3. Revue hebdomadaire du journal d'audit et des fausses alertes par le
   superviseur.
4. Test de restauration d'une sauvegarde une fois par trimestre.
5. Désigner un responsable du traitement des données au sein de la Mairie.
