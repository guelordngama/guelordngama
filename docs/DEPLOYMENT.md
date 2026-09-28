# Déploiement SafeCity

## Option A — Docker (recommandé)

Prérequis : Docker + Docker Compose.

```bash
# 1. Générer un secret et définir les variables
export SAFECITY_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SAFECITY_CORS_ORIGINS="https://safecity.example.org"
export POSTGRES_PASSWORD="un-mot-de-passe-solide"

# 2. Démarrer backend + PostgreSQL
docker compose up --build -d

# 3. Vérifier
curl http://localhost:5000/api/health
```

Le compose lance PostgreSQL, attend qu'il soit prêt, puis le backend (Waitress)
avec `SAFECITY_SEED_DEMO=false`. Volumes persistants : `pgdata`, `uploads`.

## Option B — Serveur classique (Waitress)

```bash
pip install -r requirements.txt psycopg2-binary
cp .env.example .env        # puis éditer .env
export SAFECITY_ENV=production
python -m backend.server
```
> `create_app()` **refuse de démarrer** si la config de production est non sûre
> (clé par défaut, CORS `*`, compte démo actif).

### Vraies websockets (optionnel)
Waitress ne gère que le *long-polling*. Pour des websockets natives :
```bash
pip install eventlet
export SAFECITY_ASYNC_MODE=eventlet
export SAFECITY_SERVER=socketio
python -m backend.server
```

### Reverse proxy (Nginx)
- Proxifier `/` et `/socket.io/` vers `127.0.0.1:5000`.
- Transmettre `X-Forwarded-For` (nécessaire à la limitation par IP).
- Terminer le **TLS** (HTTPS) au niveau du proxy.

## Application citoyenne (Web)

Fichiers statiques `web/` servis par n'importe quel serveur (Nginx, Netlify,
GitHub Pages…). Configurer l'URL du backend :
```js
localStorage.setItem('safecity_api', 'https://api.mondomaine.org');
```
> Géolocalisation et micro exigent **HTTPS** (sauf `localhost`).

## Poste opérateur (bureau)

```bash
pip install PySide6 "python-socketio[client]>=5.12"
export SAFECITY_API="https://api.mondomaine.org"
python -m desktop.main
```

### Exécutable Windows (PyInstaller)
Double-cliquer `desktop\windows\construire_exe.bat` (sur un poste Windows avec
Python 3.10+). Commande équivalente :
```bat
py -3 -m PyInstaller --noconfirm --clean --windowed --name SafeCityOperateur ^
  --paths desktop ^
  --add-data "desktop\map.html;." ^
  --add-data "desktop\vendor;vendor" ^
  desktop\main.py
```
L'exécutable se trouve dans `dist/SafeCityOperateur/` et le script produit
`SafeCityOperateur-<version>.zip` à distribuer. `--paths desktop` est
indispensable (sinon `pages`/`widgets` manquent) ; `map.html` et `vendor/` vont
à la racine du paquet (là où la carte les cherche).

### Mettre à jour les postes
- **Installation par le code** : double-cliquer `desktop\windows\mettre_a_jour.bat`
  (récupère la dernière version, met à jour les composants, relance le poste).
- **Exécutable** : fermer SafeCity, remplacer le dossier `SafeCityOperateur` par
  celui du nouveau ZIP, relancer `SafeCityOperateur.exe`.

Les réglages du poste (serveur, thème, son, notifications) sont conservés : ils
sont stockés dans Windows, pas dans le dossier de l'application. Vérifier la
version dans **À propos**. Mettre à jour le serveur **avant** les postes.

## Migrations de base de données

Le schéma est créé automatiquement (`db.create_all()`). Pour faire évoluer un
schéma existant en production, ajouter **Alembic / Flask-Migrate** :
```bash
pip install Flask-Migrate
```

## Liste de contrôle production
Voir [SECURITY.md](SECURITY.md#liste-de-contrôle-avant-mise-en-production).
