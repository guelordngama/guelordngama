"""Modèles de données SafeCity (SQLAlchemy).

Entités :
  - User  : citoyens et opérateurs du centre de surveillance
  - Team   : équipes / patrouilles d'intervention
  - Alert  : alertes d'urgence émises par les citoyens

Des index sont posés sur les colonnes les plus filtrées (statut, date, type)
pour garder de bonnes performances quand le volume d'alertes grandit.
"""
from datetime import datetime

from .extensions import db

# Types de danger acceptés (correspond au sélecteur de l'app citoyenne).
DANGER_TYPES = ["vol", "braquage", "incendie", "accident", "violence", "autre"]

# Cycle de vie d'une alerte.
ALERT_STATUSES = ["active", "assignee", "cloturee"]

# Rôles utilisateurs (du moins au plus privilégié).
ROLES = ["citizen", "agent", "operator", "supervisor", "admin"]

# Permissions par rôle (utilisées côté UI et contrôle d'accès).
ROLE_PERMISSIONS = {
    "admin": ["view", "assign", "close", "manage_agents", "manage_users", "settings", "reports"],
    "supervisor": ["view", "assign", "close", "manage_agents", "reports"],
    "operator": ["view", "assign", "close", "reports"],
    "agent": ["view"],
    "citizen": [],
}


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(160), unique=True, index=True)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20), default="citizen", nullable=False, index=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    # --- Suivi opérationnel des agents d'intervention ---
    availability = db.Column(db.String(20), default="offline")  # available|busy|offline
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    last_seen = db.Column(db.DateTime)
    distance_total_m = db.Column(db.Float, default=0.0)  # distance cumulée (analytics)
    current_alert_id = db.Column(db.Integer)

    alerts = db.relationship("Alert", backref="reporter", lazy=True,
                             foreign_keys="Alert.reporter_id")

    @property
    def permissions(self):
        return ROLE_PERMISSIONS.get(self.role, [])

    def to_dict(self, with_tracking=False):
        d = {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "role": self.role,
            "active": self.active,
            "permissions": self.permissions,
            "created_at": _iso(self.created_at),
        }
        if with_tracking:
            d.update({
                "availability": self.availability,
                "lat": self.lat,
                "lng": self.lng,
                "last_seen": _iso(self.last_seen),
                "current_alert_id": self.current_alert_id,
                "distance_total_m": round(self.distance_total_m or 0.0, 1),
            })
        return d


class Team(TimestampMixin, db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    patrol_lat = db.Column(db.Float)
    patrol_lng = db.Column(db.Float)
    status = db.Column(db.String(20), default="available", nullable=False)  # available | busy

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "patrol_lat": self.patrol_lat,
            "patrol_lng": self.patrol_lng,
            "status": self.status,
        }


class Alert(TimestampMixin, db.Model):
    __tablename__ = "alerts"
    __table_args__ = (
        db.Index("ix_alerts_status_created", "status", "created_at"),
        db.Index("ix_alerts_type_created", "type", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(30), nullable=False, default="autre", index=True)
    description = db.Column(db.Text)

    # Localisation
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(255))
    neighborhood = db.Column(db.String(120), index=True)  # quartier / commune

    # Informations sur le citoyen déclarant (optionnelles)
    reporter_name = db.Column(db.String(120))
    reporter_phone = db.Column(db.String(40))

    # Pièces jointes (chemins relatifs dans /uploads)
    photo_path = db.Column(db.String(255))
    audio_path = db.Column(db.String(255))

    # Résultat de l'analyse IA
    urgency = db.Column(db.String(20), default="moyenne")  # faible|moyenne|haute|critique
    ai_score = db.Column(db.Float, default=0.0)
    ai_category = db.Column(db.String(30))

    # Suivi opérationnel
    status = db.Column(db.String(20), default="active", nullable=False, index=True)
    assigned_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    assigned_agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    accepted_at = db.Column(db.DateTime)   # prise en charge par un agent
    distance_m = db.Column(db.Float)
    eta_moto_min = db.Column(db.Float)
    eta_walk_min = db.Column(db.Float)

    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    closed_at = db.Column(db.DateTime)

    assigned_team = db.relationship("Team")
    assigned_agent = db.relationship("User", foreign_keys=[assigned_agent_id])

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "lat": self.lat,
            "lng": self.lng,
            "address": self.address,
            "neighborhood": self.neighborhood,
            "reporter_name": self.reporter_name or "Citoyen anonyme",
            "reporter_phone": self.reporter_phone,
            "photo_url": f"/uploads/{self.photo_path}" if self.photo_path else None,
            "audio_url": f"/uploads/{self.audio_path}" if self.audio_path else None,
            "urgency": self.urgency,
            "ai_score": round(self.ai_score or 0.0, 3),
            "ai_category": self.ai_category,
            "status": self.status,
            "assigned_team": self.assigned_team.to_dict() if self.assigned_team else None,
            "assigned_agent": (
                {"id": self.assigned_agent.id, "name": self.assigned_agent.name}
                if self.assigned_agent else None
            ),
            "distance_m": round(self.distance_m, 1) if self.distance_m is not None else None,
            "eta_moto_min": self.eta_moto_min,
            "eta_walk_min": self.eta_walk_min,
            "created_at": _iso(self.created_at),
            "accepted_at": _iso(self.accepted_at),
            "closed_at": _iso(self.closed_at),
            "time": self.created_at.strftime("%Hh%M") if self.created_at else None,
        }


def _iso(dt):
    return dt.isoformat() if dt else None
