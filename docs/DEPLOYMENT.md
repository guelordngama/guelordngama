# Déploiement SafeCity

## 1. Backend en production

### PostgreSQL
```bash
pip install psycopg2-binary
export DATABASE_URL="postgresql+psycopg2://user:motdepasse@localhost:5432/safecity"
export SAFECITY_ENV=production
export SAFECITY_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

### Serveur Waitress (recommandé sous Windows)
```bash
export SAFECITY_SERVER=waitress
export SAFECITY_PORT=5000
python -m backend.server
```
> Waitress sert l'API et le transport Socket.IO en **long-polling** (fonctionne
> partout). Pour de vraies **websockets**, installez `eventlet` et lancez :
> ```bash
> pip install eventlet
> export SAFECITY_ASYNC_MODE=eventlet
> export SAFECITY_SERVER=socketio
> python -m backend.server
> ```

### Derrière un reverse proxy (Nginx)
- Proxifier `/` et `/socket.io/` vers le backend.
- Pour les websockets, ajouter les en-têtes `Upgrade` / `Connection`.

## 2. Application citoyenne (Web)

Fichiers statiques (`web/`) servis par n'importe quel serveur web
(Nginx, Apache, GitHub Pages, Netlify…). Configurer l'URL du backend :
```js
localStorage.setItem('safecity_api', 'https://api.mondomaine.org');
```
ou modifier `web/js/config.js`.

> ⚠️ La géolocalisation et le microphone nécessitent un contexte **HTTPS**
> (sauf `localhost`).

## 3. Application bureau (poste opérateur)

### Exécution
```bash
pip install PySide6
export SAFECITY_API="https://api.mondomaine.org"
python -m desktop.main
```

### Génération d'un exécutable Windows (PyInstaller)
```bash
pip install pyinstaller PySide6
pyinstaller --noconfirm --windowed --name SafeCityOperateur ^
  --add-data "desktop/map.html;desktop" ^
  desktop/main.py
```
- `--windowed` : pas de console.
- `--add-data` : embarque `map.html` (séparateur `;` sous Windows, `:` sous Linux/macOS).
- L'exécutable se trouve dans `dist/SafeCityOperateur/`.

> Qt WebEngine augmente la taille du binaire (~150–250 Mo). Vérifier que les
> ressources `QtWebEngineProcess` sont bien incluses dans `dist/`.

## 4. Notifications (extension)

L'architecture prévoit **Firebase Cloud Messaging** pour notifier les
opérateurs mobiles. Point d'intégration : après l'`emit('new_alert', …)` dans
`backend/app.py`, appeler l'API FCM avec la charge utile de l'alerte.

## 5. Liste de contrôle production

- [ ] `SAFECITY_SECRET_KEY` unique et secret (≥ 32 octets).
- [ ] `DATABASE_URL` PostgreSQL avec sauvegardes régulières.
- [ ] HTTPS (certificat TLS) sur le backend et l'app web.
- [ ] Changer le mot de passe du compte opérateur de démonstration.
- [ ] Restreindre `cors_allowed_origins` aux domaines légitimes.
- [ ] Journalisation et supervision (uptime, erreurs).
