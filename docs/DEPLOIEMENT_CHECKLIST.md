# ✅ Checklist de déploiement SafeCity (production — mairie)

Suivez les étapes **dans l'ordre**. Cochez au fur et à mesure. Temps estimé :
30–45 min. Tout ce qui est entre `<…>` est à remplacer par vos valeurs.

---

## 0. Prérequis (à préparer AVANT de commencer)

- [ ] **Un serveur VPS** (ex. Contabo, Ubuntu 22.04+) avec accès `root` en SSH.
- [ ] **L'IP publique du serveur** (ex. `169.58.47.76`).
- [ ] **Un nom de domaine** pointant vers cette IP. Sans domaine acheté :
  - **DuckDNS** (gratuit) : créez `<nom>.duckdns.org` → votre IP, ou
  - **sslip.io** (aucun réglage) : `169-58-47-76.sslip.io`.
- [ ] **Un compte Gmail + « mot de passe d'application »** (pour « mot de passe
  oublié ») — [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
- [ ] **Un compte SMS Africa's Talking** ([africastalking.com](https://africastalking.com))
  pour la vérification des numéros (OTP) : notez votre **username** et votre
  **API key**. Testez d'abord avec `username=sandbox`. *(Peut être ajouté plus tard.)*
- [ ] **Générer deux secrets** (gardez-les de côté) :
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY
  python3 -c "import secrets; print(secrets.token_hex(16))"   # mot de passe Postgres
  ```

---

## 1. Vérifier le DNS

- [ ] `ping <votre-domaine>` renvoie bien l'IP de votre serveur.
      *(DuckDNS : mettez à jour le champ « current ip » sur duckdns.org.)*

## 2. Se connecter au serveur et récupérer le code

```bash
ssh root@<IP-du-serveur>
apt update && apt install -y git
git clone <URL-de-votre-dépôt> safecity && cd safecity
git checkout claude/safecity-alert-platform-yohh1v   # ou main si déjà fusionné
```
- [ ] Le dossier `safecity` contient bien `deploy/`, `backend/`, `docker-compose.prod.yml`.

## 3. Ouvrir les ports 80 et 443

- [ ] Dans le panneau de votre hébergeur (et/ou `ufw allow 80,443/tcp`), les
      ports **80** et **443** sont ouverts.

## 4. Installation en une commande

```bash
sudo bash deploy/install.sh
```
Le script installe Docker, pose les questions (domaine, e-mail), génère les
secrets, émet le certificat HTTPS et démarre toute la pile.

- [ ] À la fin, il affiche `Installation terminée` avec les 3 URLs.

> 💡 **Vous préférez tout contrôler ?** Voir la section « Manuel » plus bas.

## 5. Compléter la configuration (`deploy/.env.prod`)

Le script a créé `deploy/.env.prod`. Complétez-le pour activer toutes les
fonctions de sécurité :

```bash
nano deploy/.env.prod
```
```ini
# Déjà rempli par le script :
SAFECITY_DOMAIN=<votre-domaine>
CERTBOT_EMAIL=<votre-email>
SAFECITY_SECRET_KEY=<secret-généré>
POSTGRES_PASSWORD=<mot-de-passe-généré>
SAFECITY_CORS_ORIGINS=https://<votre-domaine>
SAFECITY_SEED_DEMO=true          # ⚠️ passez à false à l'étape 7

# À AJOUTER pour un usage réel :
SAFECITY_STAFF_INVITE_CODE=<code-secret-du-personnel>     # création de comptes opérateur
SAFECITY_SMTP_HOST=smtp.gmail.com                         # mot de passe oublié
SAFECITY_SMTP_PORT=587
SAFECITY_SMTP_TLS=true
SAFECITY_SMTP_USER=<votre-gmail>
SAFECITY_SMTP_PASSWORD=<mot-de-passe-application-16-car>
SAFECITY_SMTP_FROM=<votre-gmail>
SAFECITY_AT_USERNAME=<votre-username-africastalking>     # OTP (vérif. téléphone)
SAFECITY_AT_API_KEY=<votre-clé-api-africastalking>
SAFECITY_AT_SENDER=SafeCity                               # sender ID (optionnel)
SAFECITY_AT_SANDBOX=false                                 # true pour tester d'abord
SAFECITY_SENTRY_DSN=<dsn-sentry>                          # (optionnel) alertes d'erreurs
SAFECITY_RETENTION_DAYS=365                               # conservation des alertes
```
- [ ] Fichier enregistré. Appliquer :
  ```bash
  docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml up -d
  ```
  *(Les migrations de schéma s'appliquent automatiquement au démarrage.)*

## 6. Vérifier que tout répond

- [ ] `https://<votre-domaine>/api/health` → `{"status":"ok"}`
- [ ] `https://<votre-domaine>/` → application citoyenne
- [ ] `https://<votre-domaine>/portal/` → portail agents
- [ ] Poste opérateur (bureau, sur un PC) se connecte :
  ```
  SAFECITY_API=https://<votre-domaine>  python -m desktop.main
  ```

## 7. Créer un vrai administrateur et désactiver la démo

```bash
Co="docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml"
$Co exec backend python -m backend.manage create-admin \
    --email admin@mairie.org --password '<MotDePasseFort>' --name 'Admin Mairie' --role admin
```
- [ ] Connexion OK avec ce compte.
- [ ] Dans `deploy/.env.prod`, mettez `SAFECITY_SEED_DEMO=false`, puis :
  ```bash
  $Co up -d
  ```
- [ ] Les comptes de démonstration ne fonctionnent plus.

## 8. Sauvegardes & purge (conformité)

- [ ] Les sauvegardes tournent : `$Co exec backup ls -lh /backups`
- [ ] **Tester une restauration** sur un environnement de test : `sh deploy/restore.sh --latest`
- [ ] **Planifier la purge de conservation** (cron, ex. tous les 1ers du mois) :
  ```bash
  crontab -e
  # ↓ ajouter
  0 3 1 * * cd /root/safecity && docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml exec -T backend python -m backend.manage purge-old
  ```

## 9. Tests fonctionnels (avec de vrais comptes)

- [ ] **Inscription citoyen** : reçoit un **code SMS**, le saisit, accède au bouton d'alerte.
- [ ] **Envoi d'une alerte** → apparaît en temps réel sur le poste opérateur.
- [ ] **Création d'un compte opérateur** avec le code d'invitation.
- [ ] **Mot de passe oublié** → e-mail reçu.
- [ ] **Supprimer mon compte** (citoyen) → compte effacé, alerte anonymisée.
- [ ] **Journal d'audit** visible par l'admin (`GET /api/audit`).

---

## 🔄 Mises à jour (après le premier déploiement)

```bash
cd /root/safecity && git pull
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml up -d --build
```
Les **migrations s'appliquent automatiquement** — aucune perte de données.

## 🩺 Dépannage rapide

| Symptôme | Piste |
|---|---|
| Certificat HTTPS non émis | DNS ne pointe pas sur l'IP / ports 80-443 fermés |
| « no such column » | reconstruire l'image : `up -d --build` (migrations) |
| SMS/OTP non reçu | Vérifier `SAFECITY_AT_USERNAME`/`AT_API_KEY` + solde Africa's Talking ; logs `… logs -f backend` |
| E-mail non envoyé | mot de passe **d'application** Gmail requis (pas le mot de passe habituel) |
| Voir les logs | `docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml logs -f backend` |

---

## 🛠️ Annexe — Installation manuelle (au lieu de l'étape 4)

```bash
apt install -y docker.io docker-compose-plugin
systemctl enable --now docker
cp deploy/.env.prod.example deploy/.env.prod && nano deploy/.env.prod   # (étape 5)
sh deploy/init-letsencrypt.sh          # certificat HTTPS + démarrage
```
Puis reprendre à l'étape 6.
