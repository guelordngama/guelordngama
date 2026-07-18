# Sécurité SafeCity

## Mesures en place

| Domaine | Mesure |
|---------|--------|
| Mots de passe | Hachage **bcrypt** (sel unique par mot de passe). |
| Sessions | **JWT** signés HS256, avec `exp`, `iss` et `sub` vérifiés. |
| Force brute | **Limitation du débit** sur `/api/auth/login` (fenêtre glissante par IP). |
| Entrées | **Validation** stricte (coordonnées, types, longueurs) côté serveur. |
| Fichiers | Uploads validés : **extension autorisée**, base64 vérifié, **taille maximale**. |
| En-têtes | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection`. |
| CORS | Origines **restreignables** par configuration (`SAFECITY_CORS_ORIGINS`). |
| Erreurs | Les traces internes sont **journalisées** mais **jamais renvoyées** au client. |
| Secrets | Fournis par variables d'environnement ; le démarrage en **production échoue** si la clé par défaut, un CORS `*` ou le compte démo sont laissés. |
| Rôles | Endpoints sensibles réservés aux rôles `operator`/`admin`. |

## Liste de contrôle avant mise en production

- [ ] `SAFECITY_ENV=production`
- [ ] `SAFECITY_SECRET_KEY` unique (≥ 32 octets) — `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] `SAFECITY_CORS_ORIGINS` limité aux domaines légitimes
- [ ] `SAFECITY_SEED_DEMO=false` (supprime le compte de démonstration)
- [ ] Base **PostgreSQL** avec sauvegardes
- [ ] **HTTPS** (TLS) devant le backend et l'app web
- [ ] Reverse proxy transmettant `X-Forwarded-For` (pour la limitation par IP)

> En production, `create_app()` **refuse de démarrer** si l'un des trois premiers
> points n'est pas respecté (voir `Config.validate()`).

## Limites connues / évolutions

- La limitation de débit est **en mémoire** (mono-processus). Pour plusieurs
  workers, utiliser un backend partagé (Redis).
- Pas encore de rotation de jetons (refresh tokens) — les JWT expirent après
  `SAFECITY_JWT_EXPIRES_HOURS`.

## Signaler une vulnérabilité

Merci de signaler tout problème de sécurité en privé au mainteneur du dépôt
plutôt que via une issue publique.
