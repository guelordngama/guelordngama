"""Données initiales : équipes de patrouille, comptes personnels de démo."""
import logging

from .extensions import db
from .models import Team, User
from .security import hash_password

log = logging.getLogger("safecity")

# Personnels de démonstration (un par rôle + quelques agents).
_DEMO_STAFF = [
    ("Administrateur Central", "admin@safecity.local", "admin"),
    ("Superviseur Nord", "superviseur@safecity.local", "supervisor"),
    ("Agent Kalala", "agent1@safecity.local", "agent"),
    ("Agent Mbayo", "agent2@safecity.local", "agent"),
    ("Agent Tshibanda", "agent3@safecity.local", "agent"),
]


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
        pwd = hash_password(config.DEMO_OPERATOR_PASSWORD)
        db.session.add(
            User(
                name="Opérateur Mairie",
                email=config.DEMO_OPERATOR_EMAIL,
                role="operator",
                password_hash=pwd,
            )
        )
        # Personnels de démonstration (même mot de passe pour la démo).
        for name, email, role in _DEMO_STAFF:
            if not User.query.filter_by(email=email).first():
                db.session.add(
                    User(name=name, email=email, role=role, password_hash=pwd)
                )
        log.info("Comptes de démonstration créés (opérateur + personnels).")

    db.session.commit()
