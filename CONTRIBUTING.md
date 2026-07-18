# Contribuer à SafeCity

Merci de votre intérêt ! Ce guide résume le fonctionnement du projet.

## Mise en route

```bash
git clone <dépôt> && cd safecity
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt pytest
python -m backend.app          # backend de dev
```

## Organisation du code

- Backend modulaire : `backend/` (factory, blueprints, services, IA). Voir
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- App citoyenne : `web/` — App bureau : `desktop/` — Tests : `tests/`.

## Conventions

- **Couche fine** dans `api/` (validation + appel service) ; la logique va dans
  `services/`.
- Toute entrée utilisateur passe par `backend/validation.py`.
- Les erreurs client utilisent les exceptions de `backend/errors.py`.
- Nommage et commentaires en cohérence avec l'existant (français côté métier).

## Tests

```bash
pytest -q                # tous les tests
python tests/test_backend.py   # sans pytest
```
Toute nouvelle fonctionnalité doit être couverte par un test. La CI
(`.github/workflows/ci.yml`) lance les tests et construit l'image Docker.

## Avant d'ouvrir une Pull Request

1. `pytest -q` passe.
2. Le backend démarre : `python -m backend.app`.
3. Pas de secret ni de fichier généré (`safecity.db`, `uploads/`) commité.
4. Message de commit clair et descriptif.
