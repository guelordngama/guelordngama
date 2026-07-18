"""Configuration centralisée du backend SafeCity.

La configuration provient des variables d'environnement, ce qui permet de
basculer entre développement (SQLite) et production (PostgreSQL) sans toucher
au code. Un fichier `.env` est chargé automatiquement s'il est présent.
"""
import os

# Chargement optionnel d'un fichier .env (python-dotenv).
try:  # pragma: no cover - dépend de l'environnement
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

_DEV_SECRET = "safecity-dev-secret-key-change-me-please-32b"


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Configuration de base commune à tous les environnements."""

    ENV = os.environ.get("SAFECITY_ENV", "development").lower()
    DEBUG = False
    TESTING = False

    # --- Sécurité ---
    SECRET_KEY = os.environ.get("SAFECITY_SECRET_KEY", _DEV_SECRET)
    JWT_SECRET = os.environ.get("SAFECITY_JWT_SECRET", SECRET_KEY)
    JWT_EXPIRES_HOURS = int(os.environ.get("SAFECITY_JWT_EXPIRES_HOURS", "12"))
    JWT_ISSUER = os.environ.get("SAFECITY_JWT_ISSUER", "safecity")

    # Limitation du taux de connexion (anti force brute).
    LOGIN_RATE_MAX = int(os.environ.get("SAFECITY_LOGIN_RATE_MAX", "8"))
    LOGIN_RATE_WINDOW = int(os.environ.get("SAFECITY_LOGIN_RATE_WINDOW", "300"))  # sec

    # Origines CORS autorisées (séparées par des virgules ; "*" = toutes).
    CORS_ORIGINS = os.environ.get("SAFECITY_CORS_ORIGINS", "*")

    # --- Base de données ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "safecity.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Fichiers / uploads ---
    UPLOAD_DIR = UPLOAD_DIR
    MAX_CONTENT_LENGTH = int(os.environ.get("SAFECITY_MAX_UPLOAD_MB", "16")) * 1024 * 1024
    ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}
    ALLOWED_AUDIO_EXT = {"webm", "ogg", "mp3", "wav", "m4a"}

    # --- Temps réel ---
    SURVEILLANCE_ROOM = "surveillance"

    # --- Pagination ---
    ALERTS_PAGE_SIZE = int(os.environ.get("SAFECITY_ALERTS_PAGE_SIZE", "50"))
    ALERTS_MAX_PAGE_SIZE = 200

    # --- Position de patrouille par défaut (fallback pour la distance) ---
    DEFAULT_PATROL_LAT = float(os.environ.get("SAFECITY_PATROL_LAT", "-4.3250"))
    DEFAULT_PATROL_LNG = float(os.environ.get("SAFECITY_PATROL_LNG", "15.3222"))

    # --- Compte opérateur de démonstration (désactivable en production) ---
    SEED_DEMO_OPERATOR = _env_bool("SAFECITY_SEED_DEMO", True)
    DEMO_OPERATOR_EMAIL = os.environ.get("SAFECITY_DEMO_EMAIL", "operateur@safecity.local")
    DEMO_OPERATOR_PASSWORD = os.environ.get("SAFECITY_DEMO_PASSWORD", "safecity123")

    # --- Journalisation ---
    LOG_LEVEL = os.environ.get("SAFECITY_LOG_LEVEL", "INFO").upper()

    # --- Notifications push (e-mail / SMS) ---
    # Niveaux d'urgence qui déclenchent une notification.
    NOTIFY_URGENCY_LEVELS = {
        s.strip() for s in os.environ.get("SAFECITY_NOTIFY_LEVELS", "haute,critique").split(",") if s.strip()
    }
    # E-mail (SMTP) — actif si SAFECITY_SMTP_HOST est défini.
    SMTP_HOST = os.environ.get("SAFECITY_SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SAFECITY_SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SAFECITY_SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SAFECITY_SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SAFECITY_SMTP_FROM", "alertes@safecity.local")
    SMTP_TLS = _env_bool("SAFECITY_SMTP_TLS", True)
    SMTP_TO = [e.strip() for e in os.environ.get("SAFECITY_SMTP_TO", "").split(",") if e.strip()]
    # SMS (Twilio) — actif si SAFECITY_TWILIO_SID est défini.
    TWILIO_SID = os.environ.get("SAFECITY_TWILIO_SID")
    TWILIO_TOKEN = os.environ.get("SAFECITY_TWILIO_TOKEN")
    TWILIO_FROM = os.environ.get("SAFECITY_TWILIO_FROM")
    TWILIO_TO = [n.strip() for n in os.environ.get("SAFECITY_TWILIO_TO", "").split(",") if n.strip()]

    @property
    def cors_origins_list(self):
        if self.CORS_ORIGINS.strip() == "*":
            return "*"
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate(self):
        """Contrôles de cohérence ; lève une erreur en production non sûre."""
        problems = []
        if self.ENV == "production":
            if self.SECRET_KEY == _DEV_SECRET:
                problems.append(
                    "SAFECITY_SECRET_KEY doit être défini (clé de dev interdite en production)."
                )
            if len(self.JWT_SECRET) < 32:
                problems.append("SAFECITY_JWT_SECRET doit faire au moins 32 caractères.")
            if self.CORS_ORIGINS.strip() == "*":
                problems.append(
                    "SAFECITY_CORS_ORIGINS ne doit pas être '*' en production."
                )
            if self.SEED_DEMO_OPERATOR:
                problems.append(
                    "Désactivez le compte démo en production (SAFECITY_SEED_DEMO=false)."
                )
        if problems:
            raise RuntimeError(
                "Configuration de production invalide :\n  - " + "\n  - ".join(problems)
            )
        return self


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SEED_DEMO_OPERATOR = True
    LOGIN_RATE_MAX = 1000  # ne pas gêner les tests


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name=None):
    name = (name or os.environ.get("SAFECITY_ENV", "development")).lower()
    return _CONFIGS.get(name, DevelopmentConfig)()
