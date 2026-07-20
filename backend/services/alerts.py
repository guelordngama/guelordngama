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
    # Notifications push (e-mail / SMS) — non bloquant, jamais fatal.
    try:
        from . import notifications
        notifications.dispatch_alert_notifications(payload)
    except Exception as e:  # pragma: no cover
        log.warning("Notifications non envoyées pour l'alerte #%s : %s", alert.id, e)
    return payload


def list_alerts(filters=None, page=1, page_size=50):
    """Liste filtrée + paginée des alertes.

    filters accepte : status, type, urgency, neighborhood, agent_id, q
    (recherche texte sur citoyen/quartier/description/téléphone), date_from,
    date_to (ISO 'YYYY-MM-DD').
    """
    from datetime import datetime

    from sqlalchemy import or_

    f = filters or {}
    query = Alert.query

    if f.get("status"):
        query = query.filter(Alert.status == f["status"])
    if f.get("type"):
        query = query.filter(Alert.type == f["type"])
    if f.get("urgency"):
        query = query.filter(Alert.urgency == f["urgency"])
    if f.get("neighborhood"):
        query = query.filter(Alert.neighborhood.ilike(f"%{f['neighborhood']}%"))
    if f.get("agent_id"):
        query = query.filter(Alert.assigned_agent_id == f["agent_id"])
    if f.get("q"):
        like = f"%{f['q']}%"
        query = query.filter(or_(
            Alert.reporter_name.ilike(like),
            Alert.reporter_phone.ilike(like),
            Alert.neighborhood.ilike(like),
            Alert.description.ilike(like),
            Alert.address.ilike(like),
        ))
    for key, op in (("date_from", ">="), ("date_to", "<=")):
        if f.get(key):
            try:
                d = datetime.fromisoformat(f[key])
                query = query.filter(Alert.created_at >= d if op == ">=" else Alert.created_at <= d)
            except ValueError:
                pass

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
    if alert.assigned_agent:
        alert.assigned_agent.availability = "available"
        alert.assigned_agent.current_alert_id = None
    db.session.commit()
    log.info("Alerte #%s clôturée", alert.id)

    payload = alert.to_dict()
    _emit("alert_updated", payload)
    return payload


def complete_intervention(alert_id, agent):
    """Un agent termine (clôture) une intervention qui lui est assignée."""
    from ..errors import ForbiddenError

    alert = get_alert(alert_id)
    agent_id = agent["uid"] if isinstance(agent, dict) else agent
    if alert.assigned_agent_id != agent_id:
        raise ForbiddenError("Cette intervention ne vous est pas assignée.")
    return close_alert(alert_id)


def assign_agent(alert_id, agent_id):
    """L'opérateur assigne une alerte à un agent précis."""
    from ..models import User

    alert = get_alert(alert_id)
    agent = db.session.get(User, agent_id)
    if not agent or agent.role == "citizen":
        raise NotFoundError("Agent introuvable.")

    alert.assigned_agent_id = agent.id
    alert.status = "assignee"
    if not alert.accepted_at:
        alert.accepted_at = datetime.utcnow()
    if agent.lat is not None and agent.lng is not None:
        dist, moto, walk = compute_intervention(agent.lat, agent.lng, alert.lat, alert.lng)
        alert.distance_m, alert.eta_moto_min, alert.eta_walk_min = dist, moto, walk
    agent.availability = "busy"
    agent.current_alert_id = alert.id
    db.session.commit()
    log.info("Alerte #%s assignée à l'agent '%s' par l'opérateur", alert.id, agent.name)

    payload = alert.to_dict()
    _emit("alert_updated", payload)
    _emit("agent_updated", agent.to_dict(with_tracking=True))
    return payload


def accept_intervention(alert_id, agent):
    """Un agent prend en charge une alerte."""
    from ..models import User

    alert = get_alert(alert_id)
    agent_obj = db.session.get(User, agent["uid"] if isinstance(agent, dict) else agent)
    if not agent_obj:
        raise NotFoundError("Agent introuvable.")

    alert.assigned_agent_id = agent_obj.id
    if alert.status == "active":
        alert.status = "assignee"
    if not alert.accepted_at:
        alert.accepted_at = datetime.utcnow()
    # Distance depuis la position connue de l'agent (si disponible).
    if agent_obj.lat is not None and agent_obj.lng is not None:
        dist, moto, walk = compute_intervention(agent_obj.lat, agent_obj.lng, alert.lat, alert.lng)
        alert.distance_m, alert.eta_moto_min, alert.eta_walk_min = dist, moto, walk
    agent_obj.availability = "busy"
    agent_obj.current_alert_id = alert.id
    db.session.commit()
    log.info("Alerte #%s prise en charge par l'agent '%s'", alert.id, agent_obj.name)

    payload = alert.to_dict()
    _emit("alert_updated", payload)
    return payload
