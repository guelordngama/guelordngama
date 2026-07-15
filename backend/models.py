"""Modèles de données SafeCity (SQLAlchemy).

Trois entités principales :
  - User  : citoyens et opérateurs du centre de surveillance
  - Team   : équipes / patrouilles d'intervention
  - Alert  : alertes d'urgence émises par les citoyens
"""
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Types de danger acceptés (correspond au sélecteur de l'app citoyenne).
DANGER_TYPES = ["vol", "braquage", "incendie", "accident", "violence", "autre"]

# Cycle de vie d'une alerte.
ALERT_STATUSES = ["active", "assignee", "cloturee"]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(160), unique=True)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20), default="citizen")  # citizen | operator | admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    alerts = db.relationship("Alert", backref="reporter", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    patrol_lat = db.Column(db.Float)
    patrol_lng = db.Column(db.Float)
    status = db.Column(db.String(20), default="available")  # available | busy
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "patrol_lat": self.patrol_lat,
            "patrol_lng": self.patrol_lng,
            "status": self.status,
        }


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(30), nullable=False, default="autre")
    description = db.Column(db.Text)

    # Localisation
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(255))
    neighborhood = db.Column(db.String(120))  # quartier

    # Pièces jointes (chemins relatifs dans /uploads)
    photo_path = db.Column(db.String(255))
    audio_path = db.Column(db.String(255))

    # Résultat de l'analyse IA
    urgency = db.Column(db.String(20), default="moyenne")  # faible | moyenne | haute | critique
    ai_score = db.Column(db.Float, default=0.0)  # confiance de classification 0..1
    ai_category = db.Column(db.String(30))  # catégorie prédite par l'IA

    # Suivi opérationnel
    status = db.Column(db.String(20), default="active")
    assigned_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    distance_m = db.Column(db.Float)  # distance équipe -> alerte (mètres)
    eta_moto_min = db.Column(db.Float)
    eta_walk_min = db.Column(db.Float)

    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    assigned_team = db.relationship("Team")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "lat": self.lat,
            "lng": self.lng,
            "address": self.address,
            "neighborhood": self.neighborhood,
            "photo_url": f"/uploads/{self.photo_path}" if self.photo_path else None,
            "audio_url": f"/uploads/{self.audio_path}" if self.audio_path else None,
            "urgency": self.urgency,
            "ai_score": round(self.ai_score or 0.0, 3),
            "ai_category": self.ai_category,
            "status": self.status,
            "assigned_team": self.assigned_team.to_dict() if self.assigned_team else None,
            "distance_m": round(self.distance_m, 1) if self.distance_m is not None else None,
            "eta_moto_min": self.eta_moto_min,
            "eta_walk_min": self.eta_walk_min,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "time": self.created_at.strftime("%Hh%M") if self.created_at else None,
        }
