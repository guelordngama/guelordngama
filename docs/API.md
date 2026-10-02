# API SafeCity — Référence

Base URL : `http://localhost:5000`

Toutes les réponses sont en JSON. Les erreurs suivent un format homogène :

```json
{ "error": { "message": "Description lisible", "code": "validation_error" } }
```

## Authentification

Les endpoints marqués 🔒 exigent un jeton JWT d'opérateur dans l'en-tête :

```
Authorization: Bearer <token>
```

---

### `POST /api/auth/login`
Connexion d'un opérateur. **Limité** (anti force brute).

**Corps :**
```json
{ "email": "operateur@safecity.local", "password": "safecity123" }
```
**200 :**
```json
{ "token": "eyJ...", "user": { "id": 1, "name": "...", "role": "operator" } }
```
**401 :** identifiants invalides · **429 :** trop de tentatives.

---

### `POST /api/auth/me/avatar` · `DELETE /api/auth/me/avatar` 🔒 (tout utilisateur connecté)
Définit ou retire **sa propre** photo de profil (citoyen ou personnel) —
jamais celle d'un tiers. **Corps (POST) :** `{ "photo": "data:image/jpeg;base64,..." }`.
**200 :** la fiche utilisateur à jour (`avatar_url` : lien signé, ~24 h, ou
`null`). L'ancien fichier est supprimé. `avatar_url` figure aussi dans
`/api/agents`, `/api/citizens` et la réponse de connexion.

---

### `POST /api/alerts`
Crée une alerte (citoyen, public).

**Corps :**
```json
{
  "type": "braquage",
  "description": "un homme armé menace la boutique",
  "lat": -4.33, "lng": 15.31,
  "address": "optionnel", "neighborhood": "optionnel",
  "photo": "data:image/jpeg;base64,...",   // optionnel
  "audio": "data:audio/webm;base64,..."     // optionnel
}
```
**201 :** l'alerte complète (avec `urgency`, `ai_category`, `distance_m`, `eta_moto_min`…).
Déclenche l'événement temps réel `new_alert`.
**400 :** coordonnées manquantes/invalides ou type de fichier refusé.

---

### `GET /api/alerts`
Liste les alertes (récentes d'abord).

**Paramètres :** `status` (`active|assignee|cloturee`), `page`, `page_size`.
- Sans `page`/`page_size` : renvoie un **tableau** simple (compatibilité).
- Avec pagination : `{ "items": [...], "page", "page_size", "total", "pages" }`.

### `GET /api/alerts/<id>`
Détail d'une alerte. **404** si absente.

### `POST /api/alerts/<id>/assign` 🔒
Affecte une équipe et recalcule la distance depuis sa position.
**Corps :** `{ "team_id": 1 }` — déclenche `alert_updated`.

### `POST /api/alerts/<id>/close` 🔒
Clôture l'alerte et libère l'équipe — déclenche `alert_updated`.

### `POST /api/alerts/<id>/false-alarm` 🔒 (opérateur, superviseur, admin)
Classe l'alerte en **fausse alerte** et la clôture (agent/patrouille libérés).
**Corps :** `{ "reason": "Canular / appel malveillant — …" }` — motif **obligatoire**
(400 sinon). Inscrit au journal (`false_alarm_marked`). Le citoyen n'est jamais
bloqué : ses alertes suivantes portent `reporter_false_alarms` (avertissement).
Filtre : `GET /api/alerts?false_alarm=1`.

### `DELETE /api/alerts/<id>/false-alarm` 🔒 (superviseur, admin)
Annule la qualification. **Corps :** `{ "reason": "…" }` (obligatoire).

### `GET /api/alerts/<id>/journal` 🔒 (personnel)
Journal de l'intervention, chronologique :
`[{ "time", "action", "label", "actor", "role", "detail", "ip" }]`
(alerte reçue, patrouille / agent affecté, acceptée, terminée, clôturée,
fausse alerte…).

### `GET /api/security/overview` 🔒 (opérateur, superviseur, admin)
Mécanismes en place (authentification, rôles et responsabilités, protection des
données, résilience) et indicateurs : connexions / échecs 24 h, actions tracées
24 h, fausses alertes 30 j, citoyens récidivistes (téléphone masqué).

### `GET /api/audit?limit=&action=&alert_id=&q=` 🔒 (superviseur, admin)
Journal d'audit complet (qui, rôle, action, détail, IP, heure).

---

### `GET /api/teams`
Liste les équipes d'intervention.

### `GET /api/stats`
Statistiques du tableau de bord (mises en cache quelques secondes) :
```json
{
  "today_count": 3, "active_count": 5, "total_count": 12,
  "by_type": { "vol": 4, "braquage": 2, ... },
  "dangerous_zones": [ { "zone": "Zone 65", "count": 3 } ],
  "last_alert": { ... }
}
```

### `GET /api/health` · `GET /api/meta`
Sonde de santé et métadonnées (types de danger, statuts).

---

## Temps réel (Socket.IO)

Salle : `surveillance` (rejointe automatiquement à la connexion).
Transport : **polling** (le backend Waitress ne gère pas les websockets).

| Événement | Sens | Charge utile |
|-----------|------|--------------|
| `new_alert` | serveur → clients | alerte complète |
| `alert_updated` | serveur → clients | alerte mise à jour |
| `connected` | serveur → client | message de bienvenue |

### `POST /api/agents` · `PATCH /api/agents/<id>` · `DELETE /api/agents/<id>` 🔒
CRUD des personnels (operator/supervisor/admin). Corps : name, email, phone,
role, password, active. Diffuse `agent_updated` / `agent_deleted`.

### `POST /api/agents/me/location` · `POST /api/agents/me/status` 🔒
Un agent envoie sa position GPS / sa disponibilité (available|busy|offline).

### `POST /api/alerts/<id>/accept` 🔒
Un agent prend en charge une intervention (statut `assignee`, distance recalculée).

### `POST /api/alerts/<id>/arrived` 🔒 (agent assigné, ou opérateur/superviseur/admin)
Signale l'arrivée sur les lieux — étape **Sur place** de la progression
(n'affecte pas `status`). **200 :** l'alerte à jour (`stage: "on_site"`,
`arrived_at`). Chaque alerte porte désormais `stage` (`received|assigned|
en_route|on_site|resolved`), `stage_label` et `progress_steps` (6 étapes,
même forme que `steps` du suivi citoyen).

### `GET /api/analytics?period=week|month|year` 🔒
Performance par agent : interventions, taux de résolution, temps de réponse,
distance parcourue.

### `GET /api/reports/pdf?period=today|month|year|all` 🔒
Rapport PDF de synthèse.

## Notifications
À l'arrivée d'une alerte (urgences configurées), envoi optionnel d'**e-mail**
(SMTP) et **SMS** (passerelle Orange RDC / HTTP générique / Africa's Talking) si
les variables correspondantes sont définies.
