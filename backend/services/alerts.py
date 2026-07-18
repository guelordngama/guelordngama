"""Service métier des alertes : création, listing, affectation, clôture.

Découplé des routes HTTP pour être testable et réutilisable. Émet les
événements temps réel vers le centre de surveillance.
"""
import logging
from datetime import datetime

from flask import current_app

from ..ai.classifier import get_classifier
from ..errors import NotFoundError
from ..extensions import db, socketio
from ..geo import compute_intervention, reverse_geocode
from ..models import Alert, Team
from ..security import save_data_url

log = logging.getLogger("safecity")


def _emit(event, payload):
    socketio.emit(event, payload, room=current_app.config["SURVEILLANCE_ROOM"])


def create_alert(data):
    """Crée une alerte à partir d'une charge utile déjà validée."""
    ai = get_classifier().classify(data["description"], data["type"])

    neighborhood, address = reverse_geocode(data["lat"], data["lng"])
    neighborhood = data.get("neighborhood") or neighborhood
    address = data.get("address") or address

    photo_path = save_data_url(data.get("photo"), "image")
    audio_path = save_data_url(data.get("audio"), "audio")

    dist, eta_moto, eta_walk = compute_intervention(
        current_app.config["DEFAULT_PATROL_LAT"],
        current_app.config["DEFAULT_PATROL_LNG"],
        data["lat"],
        data["lng"],
    )

    alert = Alert(
        type=data["type"],
        description=data["description"],
        lat=data["lat"],
        lng=data["lng"],
        address=address,
        neighborhood=neighborhood,
        reporter_name=data.get("reporter_name"),
        reporter_phone=data.get("reporter_phone"),
        photo_path=photo_path,
        audio_path=audio_path,
        urgency=ai["urgency"],
        ai_score=ai["score"],
        ai_category=ai["category"],
        status="active",
        distance_m=dist,
        eta_moto_min=eta_moto,
        eta_walk_min=eta_walk,
        reporter_id=data.get("reporter_id"),
    )
    db.session.add(alert)
    db.session.commit()
    log.info("Nouvelle alerte #%s type=%s urgence=%s", alert.id, alert.type, alert.urgency)

    payload = alert.to_dict()
    _emit("new_alert", payload)
    return payload


def list_alerts(status=None, page=1, page_size=50):
    query = Alert.query
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(Alert.created_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    return {
        "items": [a.to_dict() for a in pagination.items],
        "page": pagination.page,
        "page_size": page_size,
        "total": pagination.total,
        "pages": pagination.pages,
    }


def get_alert(alert_id):
    alert = db.session.get(Alert, alert_id)
    if not alert:
        raise NotFoundError("Alerte introuvable.")
    return alert


def assign_team(alert_id, team_id):
    alert = get_alert(alert_id)
    team = db.session.get(Team, team_id)
    if not team:
        raise NotFoundError("Équipe introuvable.")

    alert.assigned_team_id = team.id
    alert.status = "assignee"
    dist, eta_moto, eta_walk = compute_intervention(
        team.patrol_lat, team.patrol_lng, alert.lat, alert.lng
    )
    alert.distance_m, alert.eta_moto_min, alert.eta_walk_min = dist, eta_moto, eta_walk
    team.status = "busy"
    db.session.commit()
    log.info("Alerte #%s affectée à l'équipe '%s'", alert.id, team.name)

    payload = alert.to_dict()
    _emit("alert_updated", payload)
    return payload


def close_alert(alert_id):
    alert = get_alert(alert_id)
    alert.status = "cloturee"
    alert.closed_at = datetime.utcnow()
    if alert.assigned_team:
        alert.assigned_team.status = "available"
    db.session.commit()
    log.info("Alerte #%s clôturée", alert.id)

    payload = alert.to_dict()
    _emit("alert_updated", payload)
    return payload
