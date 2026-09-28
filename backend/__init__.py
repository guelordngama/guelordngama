"""SafeCity — fabrique d'application Flask (application factory).

Usage :
    from backend import create_app, socketio
    app = create_app()
    socketio.run(app)
"""
from .config import get_config
from .extensions import cors, db, migrate, socketio

__version__ = "1.23.0"
__all__ = ["create_app", "socketio", "db", "__version__"]


def create_app(config=None):
    from flask import Flask

    from .api import register_blueprints
    from .errors import register_error_handlers
    from .logging_config import setup_logging
    from .observability import init_sentry
    from .realtime import register_socket_events
    from .seed import seed_defaults

    config = config or get_config()
    config.validate()  # refuse de démarrer si la config de prod est non sûre

    log = setup_logging(config.LOG_LEVEL)
    init_sentry(config)  # suivi d'erreurs (actif si SAFECITY_SENTRY_DSN défini)
    if config.ENV == "production" and config.SEED_DEMO_OPERATOR:
        log.warning(
            "Compte de démonstration ACTIF en production (SAFECITY_SEED_DEMO=true). "
            "À désactiver après avoir créé un vrai administrateur "
            "(python -m backend.manage create-admin)."
        )

    app = Flask(__name__, static_folder=None)
    app.config.from_object(config)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)  # commandes « flask db … » (migrations Alembic)
    cors.init_app(app, resources={r"/api/*": {"origins": config.cors_origins_list},
                                  r"/uploads/*": {"origins": config.cors_origins_list}})
    socketio.init_app(app, cors_allowed_origins=config.cors_origins_list)

    # En-têtes de sécurité sur toutes les réponses
    _register_security_headers(app)

    # Blueprints + erreurs + temps réel
    register_blueprints(app)
    register_error_handlers(app)
    register_socket_events()

    # Base de données + données initiales + modèle IA
    with app.app_context():
        from .ai.classifier import get_classifier
        from . import models  # noqa: F401  (enregistre les tables)

        # En production, le schéma est géré par les migrations Alembic
        # (`flask db upgrade`, lancé au déploiement) : pas de create_all() qui
        # empêcherait toute évolution ultérieure sans perte de données.
        # En développement/test, create_all() garde un démarrage immédiat.
        if config.ENV != "production":
            db.create_all()
            # create_all() ne modifie pas une table existante : on ajoute les
            # colonnes récentes à une base locale plus ancienne (dev seulement).
            _add_missing_columns(log)
        try:
            seed_defaults(config)
            get_classifier()  # entraîne le classifieur une fois au démarrage
        except Exception as e:
            # Peut arriver avant le premier « flask db upgrade » (tables absentes).
            db.session.rollback()
            log.warning(
                "Amorçage différé — appliquez les migrations (flask db upgrade). "
                "Détail : %s", e)

    return app


def _add_missing_columns(log):
    """Développement : ajoute aux tables existantes les colonnes du modèle qui
    leur manquent (ex. base SQLite locale créée avant une mise à jour).
    En production, le schéma est géré par les migrations (flask db upgrade)."""
    import sqlalchemy as sa

    engine = db.engine
    insp = sa.inspect(engine)
    for table in db.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" ' \
                  f"{col.type.compile(dialect=engine.dialect)}"
            if not col.nullable:
                if isinstance(col.type, sa.Boolean):
                    ddl += " NOT NULL DEFAULT " + ("0" if engine.dialect.name == "sqlite"
                                                   else "false")
                else:
                    log.warning("Colonne %s.%s non ajoutée (NOT NULL sans défaut) : "
                                "appliquez les migrations.", table.name, col.name)
                    continue
            with engine.begin() as conn:
                conn.execute(sa.text(ddl))
            log.info("Base locale mise à jour : colonne %s.%s ajoutée.", table.name, col.name)


def _register_security_headers(app):
    @app.after_request
    def set_secure_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
        return resp
