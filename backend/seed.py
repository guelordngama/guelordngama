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
    ("Agent Kalala", "agent1@safecity.local", "agent", -11.6600, 27.4790, "available"),
    ("Agent Mbayo", "agent2@safecity.local", "agent", -11.6525, 27.5000, "available"),
    ("Agent Tshibanda", "agent3@safecity.local", "agent", -11.6865, 27.4570, "available"),
]


# Une patrouille par commune de Lubumbashi (nom, lat, lng). Les positions sont
# des points de départ approximatifs dans chaque commune ; elles se mettent à
# jour avec les positions réelles des patrouilles.
COMMUNE_PATROLS = [
    ("Lubumbashi", -11.6647, 27.4794),
    ("Kamalondo", -11.6560, 27.4640),
    ("Katuba", -11.6870, 27.4560),
    ("Kenya", -11.6520, 27.5010),
    ("Kampemba", -11.6400, 27.4900),
    ("Ruashi", -11.6150, 27.5450),
    ("Annexe", -11.6950, 27.5100),
]


def ensure_commune_patrols():
    """Garantit une patrouille « Patrouille <commune> » pour chacune des 7
    communes (sans toucher aux équipes existantes ni créer de doublon)."""
    existing = {t.name.strip().lower() for t in Team.query.all()}
    added = 0
    for commune, lat, lng in COMMUNE_PATROLS:
        name = f"Patrouille {commune}"
        if name.lower() not in existing:
            db.session.add(Team(name=name, patrol_lat=lat, patrol_lng=lng))
            added += 1
    if added:
        log.info("Patrouilles de commune ajoutées : %d.", added)


def seed_defaults(config):
    ensure_commune_patrols()

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
