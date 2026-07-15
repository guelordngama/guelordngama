"""Configuration centralisée du backend SafeCity.

La configuration se fait via variables d'environnement pour permettre
un basculement simple entre le prototype (SQLite) et la production
(PostgreSQL) sans modifier le code.
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class Config:
    """Configuration de base commune à tous les environnements."""

    # --- Sécurité ---
    # Clé de développement (>= 32 octets). À REMPLACER en production via
    # la variable d'environnement SAFECITY_SECRET_KEY.
    SECRET_KEY = os.environ.get(
        "SAFECITY_SECRET_KEY", "safecity-dev-secret-key-change-me-please-32b"
    )
    JWT_SECRET = os.environ.get("SAFECITY_JWT_SECRET", SECRET_KEY)
    JWT_EXPIRES_HOURS = int(os.environ.get("SAFECITY_JWT_EXPIRES_HOURS", "12"))

    # --- Base de données ---
    # Prototype : SQLite (fichier local). Production : PostgreSQL via DATABASE_URL.
    #   export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/safecity"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "safecity.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Fichiers ---
    UPLOAD_DIR = UPLOAD_DIR
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 Mo max par requête

    # --- Temps réel ---
    # Salle SocketIO du centre de surveillance (mairie).
    SURVEILLANCE_ROOM = "surveillance"

    # --- Position de référence de la patrouille par défaut (fallback) ---
    # Utilisée pour le calcul de distance quand aucune équipe n'est assignée.
    DEFAULT_PATROL_LAT = float(os.environ.get("SAFECITY_PATROL_LAT", "-4.3250"))
    DEFAULT_PATROL_LNG = float(os.environ.get("SAFECITY_PATROL_LNG", "15.3222"))


class ProductionConfig(Config):
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


def get_config():
    env = os.environ.get("SAFECITY_ENV", "development").lower()
    return ProductionConfig if env == "production" else DevelopmentConfig
