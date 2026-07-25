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

    # --- Création de comptes personnels (console bureau) ---
    # Code d'invitation exigé pour créer un compte opérateur depuis le bureau.
    # Si vide, l'auto-inscription du personnel est DÉSACTIVÉE (sécurité par
    # défaut) : seuls les administrateurs créent des comptes (backend.manage).
    STAFF_INVITE_CODE = os.environ.get("SAFECITY_STAFF_INVITE_CODE", "").strip()

    # --- Compte opérateur de démonstration (désactivable en production) ---
    SEED_DEMO_OPERATOR = _env_bool("SAFECITY_SEED_DEMO", True)
    DEMO_OPERATOR_EMAIL = os.environ.get("SAFECITY_DEMO_EMAIL", "operateur@safecity.local")
    DEMO_OPERATOR_PASSWORD = os.environ.get("SAFECITY_DEMO_PASSWORD", "safecity123")

    # --- Journalisation ---
    LOG_LEVEL = os.environ.get("SAFECITY_LOG_LEVEL", "INFO").upper()

    # --- Suivi d'erreurs (Sentry) — actif si un DSN est fourni ---
    SENTRY_DSN = os.environ.get("SAFECITY_SENTRY_DSN")
    SENTRY_TRACES_RATE = float(os.environ.get("SAFECITY_SENTRY_TRACES_RATE", "0.0"))

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
    # Nom affiché de l'expéditeur (ex. « SafeCity Lubumbashi <adresse> »).
    SMTP_FROM_NAME = os.environ.get("SAFECITY_SMTP_FROM_NAME", "SafeCity Lubumbashi")
    SMTP_TLS = _env_bool("SAFECITY_SMTP_TLS", True)
    SMTP_TO = [e.strip() for e in os.environ.get("SAFECITY_SMTP_TO", "").split(",") if e.strip()]
    # Destinataires SMS des alertes (superviseurs sur le terrain), envoyés via la
    # passerelle SMS configurée ci-dessous. Vide = pas d'alerte par SMS.
    SMS_ALERT_TO = [n.strip() for n in os.environ.get("SAFECITY_SMS_ALERT_TO", "").split(",") if n.strip()]

    # --- SMS via l'API Orange (opérateur majeur en RDC) ---
    # Recommandé pour la RDC : Orange RD Congo dispose d'une API SMS officielle.
    # Actif si SAFECITY_ORANGE_CLIENT_ID et SAFECITY_ORANGE_CLIENT_SECRET sont
    # définis. Le jeton OAuth2 est obtenu automatiquement (client_credentials).
    ORANGE_CLIENT_ID = os.environ.get("SAFECITY_ORANGE_CLIENT_ID")
    ORANGE_CLIENT_SECRET = os.environ.get("SAFECITY_ORANGE_CLIENT_SECRET")
    # Adresse expéditrice déclarée chez Orange (ex "tel:+243999999999" ou un nom court).
    ORANGE_SENDER = os.environ.get("SAFECITY_ORANGE_SENDER", "")
    ORANGE_TOKEN_URL = os.environ.get(
        "SAFECITY_ORANGE_TOKEN_URL", "https://api.orange.com/oauth/v3/token")
    ORANGE_SMS_URL = os.environ.get(
        "SAFECITY_ORANGE_SMS_URL", "https://api.orange.com/smsmessaging/v1/outbound")

    # --- Passerelle SMS HTTP générique (autre agrégateur/opérateur local RDC) ---
    # Active si SAFECITY_SMS_HTTP_URL est défini. Convient à la plupart des
    # agrégateurs (Vodacom/Airtel/Orange via une API HTTP) : on mappe les noms
    # de champs « destinataire » et « message », plus des paramètres statiques.
    SMS_HTTP_URL = os.environ.get("SAFECITY_SMS_HTTP_URL")
    SMS_HTTP_METHOD = os.environ.get("SAFECITY_SMS_HTTP_METHOD", "POST").upper()
    SMS_HTTP_TO_PARAM = os.environ.get("SAFECITY_SMS_HTTP_TO_PARAM", "to")
    SMS_HTTP_TEXT_PARAM = os.environ.get("SAFECITY_SMS_HTTP_TEXT_PARAM", "message")
    SMS_HTTP_JSON = _env_bool("SAFECITY_SMS_HTTP_JSON", False)
    SMS_HTTP_EXTRA = os.environ.get("SAFECITY_SMS_HTTP_EXTRA", "")  # "api_key=xxx&sender=SafeCity"
    SMS_HTTP_AUTH_HEADER = os.environ.get("SAFECITY_SMS_HTTP_AUTH_HEADER")  # ex "Bearer xxx"

    # --- SMS via Africa's Talking (agrégateur régional) ---
    # Actif si SAFECITY_AT_USERNAME et SAFECITY_AT_API_KEY sont définis.
    # Bac à sable : username=sandbox (ou SAFECITY_AT_SANDBOX=true).
    AT_USERNAME = os.environ.get("SAFECITY_AT_USERNAME")
    AT_API_KEY = os.environ.get("SAFECITY_AT_API_KEY")
    AT_SENDER = os.environ.get("SAFECITY_AT_SENDER")  # sender ID / short code (optionnel)
    AT_SANDBOX = _env_bool("SAFECITY_AT_SANDBOX", False)

    # --- Vérification du téléphone (OTP) ---
    OTP_LENGTH = int(os.environ.get("SAFECITY_OTP_LENGTH", "6"))
    OTP_TTL_MIN = int(os.environ.get("SAFECITY_OTP_TTL_MIN", "10"))
    OTP_MAX_ATTEMPTS = int(os.environ.get("SAFECITY_OTP_MAX_ATTEMPTS", "5"))

    # --- Conservation des données (conformité) ---
    # Durée de conservation des alertes clôturées avant purge (jours).
    RETENTION_DAYS = int(os.environ.get("SAFECITY_RETENTION_DAYS", "365"))

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
            # Le compte démo en production n'est pas bloquant, mais fortement
            # déconseillé : on le signale plus bas (avertissement).
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
    # Tests hermétiques : on ignore toute passerelle e-mail/SMS issue d'un .env
    # local, pour que les tests ne dépendent pas de la configuration de la machine.
    SMTP_HOST = None
    SMS_HTTP_URL = None
    ORANGE_CLIENT_ID = None
    ORANGE_CLIENT_SECRET = None
    AT_USERNAME = None
    AT_API_KEY = None


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name=None):
    name = (name or os.environ.get("SAFECITY_ENV", "development")).lower()
    return _CONFIGS.get(name, DevelopmentConfig)()
