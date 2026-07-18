"""Enregistrement des blueprints de l'API SafeCity."""


def register_blueprints(app):
    from .agents import bp as agents_bp
    from .alerts import bp as alerts_bp
    from .auth import bp as auth_bp
    from .health import bp as health_bp
    from .stats import bp as stats_bp
    from .teams import bp as teams_bp
    from .uploads import bp as uploads_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(uploads_bp)
