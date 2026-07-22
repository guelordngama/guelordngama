"""Enregistrement des blueprints de l'API SafeCity."""


def register_blueprints(app):
    from .agents import bp as agents_bp
    from .alerts import bp as alerts_bp
    from .audit import bp as audit_bp
    from .auth import bp as auth_bp
    from .export import bp as export_bp
    from .health import bp as health_bp
    from .messages import bp as messages_bp
    from .reports import bp as reports_bp
    from .stats import bp as stats_bp
    from .teams import bp as teams_bp
    from .uploads import bp as uploads_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(audit_bp)

    # En développement, le backend sert aussi les fronts (app citoyenne au « / »,
    # portail au « /portal/ ») pour tout avoir sur la même origine (pas de CORS).
    # En production, Nginx s'en charge : on n'enregistre donc pas ces routes.
    if str(app.config.get("ENV", "development")).lower() != "production":
        from .webapp import bp as frontend_bp
        app.register_blueprint(frontend_bp)
