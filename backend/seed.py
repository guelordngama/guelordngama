"""Données initiales : équipes de patrouille, comptes personnels de démo."""
import logging

from .extensions import db
from .models import Team, User
from .security import hash_password

log = logging.getLogger("safecity")

# Personnels de démonstration (nom, email, rôle, lat, lng, disponibilité).
_DEMO_STAFF = [
    ("Administrateur Central", "admin@safecity.local", "admin", None, None, "offline"),
    ("Superviseur Nord", "superviseur@safecity.local", "supervisor", None, None, "offline"),
    ("Agent Kalala", "agent1@safecity.local", "agent", -4.3210, 15.3120, "available"),
    ("Agent Mbayo", "agent2@safecity.local", "agent", -4.3320, 15.3280, "available"),
    ("Agent Tshibanda", "agent3@safecity.local", "agent", -4.3080, 15.3050, "available"),
]


def seed_defaults(config):
    if Team.query.count() == 0:
        # Équipes de patrouille situées à LUBUMBASHI (déploiement mairie).
        db.session.add_all(
            [
                Team(name="Patrouille Centre-Ville", patrol_lat=-11.6647, patrol_lng=27.4794),
                Team(name="Patrouille Kenya", patrol_lat=-11.6520, patrol_lng=27.5010),
                Team(name="Patrouille Katuba", patrol_lat=-11.6870, patrol_lng=27.4560),
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
        from datetime import datetime

        for name, email, role, lat, lng, avail in _DEMO_STAFF:
            if not User.query.filter_by(email=email).first():
                db.session.add(User(
                    name=name, email=email, role=role, password_hash=pwd,
                    lat=lat, lng=lng, availability=avail,
                    last_seen=datetime.utcnow() if avail != "offline" else None,
                ))
        log.info("Comptes de démonstration créés (opérateur + personnels).")

    db.session.commit()
