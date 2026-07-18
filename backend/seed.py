"""Données initiales : équipes de patrouille et compte opérateur de démo."""
import logging

from .extensions import db
from .models import Team, User
from .security import hash_password

log = logging.getLogger("safecity")


def seed_defaults(config):
    if Team.query.count() == 0:
        db.session.add_all(
            [
                Team(name="Patrouille Avenue Lumumba", patrol_lat=-4.3217, patrol_lng=15.3125),
                Team(name="Patrouille Centre-Ville", patrol_lat=-4.3050, patrol_lng=15.3080),
                Team(name="Patrouille Kenya", patrol_lat=-4.3400, patrol_lng=15.3300),
            ]
        )
        log.info("Équipes de patrouille initialisées.")

    if config.SEED_DEMO_OPERATOR and User.query.filter_by(role="operator").count() == 0:
        db.session.add(
            User(
                name="Opérateur Mairie",
                email=config.DEMO_OPERATOR_EMAIL,
                role="operator",
                password_hash=hash_password(config.DEMO_OPERATOR_PASSWORD),
            )
        )
        log.info("Compte opérateur de démonstration créé (%s).", config.DEMO_OPERATOR_EMAIL)

    db.session.commit()
