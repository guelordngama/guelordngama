"""Service métier des alertes : création, listing, affectation, clôture.

Découplé des routes HTTP pour être testable et réutilisable. Émet les
événements temps réel vers le centre de surveillance.
"""
import logging
import secrets
from datetime import datetime

from flask import current_app

from ..ai.classifier import get_classifier
from ..errors import NotFoundError
from ..extensions import db, socketio
from ..geo import compute_intervention, haversine_m, reverse_geocode
from ..models import Alert, Team
from ..security import save_data_url

log = logging.getLogger("safecity")


def _emit(event, payload):
    socketio.emit(event, payload, room=current_app.config["SURVEILLANCE_ROOM"])


# Alphabet sans caractères ambigus (0/O, 1/I) pour une référence facile à noter.
_REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_ref():
    """Référence publique unique et lisible, ex. « SC-K7P2Q9 »."""
    for _ in range(10):
        code = "SC-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(6))
        if not Alert.query.filter_by(public_ref=code).first():
            return code
    # Repli extrêmement improbable : ajoute de l'entropie.
    return "SC-" + secrets.token_hex(5).upper()


def track_alert(reference):
    """Suivi citoyen d'une alerte par sa référence publique. Renvoie une vue
    minimale (aucune donnée sensible) ou None si la référence est inconnue."""
    if not reference:
        return None
    alert = Alert.query.filter_by(public_ref=reference.strip().upper()).first()
    if not alert:
        return None
    # Si l'alerte est un doublon, elle suit l'avancement de l'incident principal
    # (c'est lui qui est traité), tout en conservant la référence du citoyen.
    incident = alert.primary if (alert.duplicate_of_id and alert.primary) else alert
    status = incident.public_status()
    status["reference"] = alert.public_ref
    return status


def _find_duplicate_primary(alert_type, lat, lng):
    """Cherche un signalement PRINCIPAL récent et proche du même type, pour
    regrouper les doublons (plusieurs citoyens signalant le même incident).
    Renvoie l'alerte principale ou None."""
    from datetime import timedelta

    if not current_app.config.get("DEDUP_ENABLED", True):
        return None
    radius = current_app.config["DEDUP_RADIUS_M"]
    window = current_app.config["DEDUP_WINDOW_MIN"]
    since = datetime.utcnow() - timedelta(minutes=window)
    # Candidats : mêmes type, encore ouverts (non clôturés), récents, et
    # eux-mêmes principaux (pas déjà des doublons).
    candidates = (
        Alert.query
        .filter(Alert.type == alert_type)
        .filter(Alert.duplicate_of_id.is_(None))
        .filter(Alert.status != "cloturee")
        .filter(Alert.created_at >= since)
        .order_by(Alert.created_at.desc())
        .limit(50)
        .all()
    )
    best, best_dist = None, None
    for c in candidates:
        if c.lat is None or c.lng is None:
            continue
        d = haversine_m(lat, lng, c.lat, c.lng)
        if d <= radius and (best_dist is None or d < best_dist):
            best, best_dist = c, d
    return best


def create_alert(data):
    """Crée une alerte à partir d'une charge utile déjà validée."""
    ai = get_classifier().classify(data["description"], data["type"])

    neighborhood, address = reverse_geocode(data["lat"], data["lng"])
    neighborhood = data.get("neighborhood") or neighborhood
    address = data.get("address") or address

    photo_path = save_data_url(data.get("photo"), "image")
    audio_path = save_data_url(data.get("audio"), "audio")
    video_path = save_data_url(data.get("video"), "video")

    dist, eta_moto, eta_walk = compute_intervention(
        current_app.config["DEFAULT_PATROL_LAT"],
        current_app.config["DEFAULT_PATROL_LNG"],
        data["lat"],
        data["lng"],
    )

    # Regroupement : cette alerte double-t-elle un incident déjà signalé ?
    primary = _find_duplicate_primary(data["type"], data["lat"], data["lng"])

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
        video_path=video_path,
        urgency=ai["urgency"],
        ai_score=ai["score"],
        ai_category=ai["category"],
        status="active",
        public_ref=_generate_ref(),
        distance_m=dist,
        eta_moto_min=eta_moto,
        eta_walk_min=eta_walk,
        reporter_id=data.get("reporter_id"),
        duplicate_of_id=primary.id if primary else None,
    )
    db.session.add(alert)
    db.session.commit()

    if primary is not None:
        # Doublon : on NE crée PAS un nouvel incident à l'écran (pas de pop-up ni
        # d'alarme redondante). On rafraîchit le signalement principal pour que le
        # compteur de signalements liés s'incrémente côté opérateur.
        log.info("Alerte #%s regroupée avec l'incident principal #%s (doublon)",
                 alert.id, primary.id)
        primary_payload = primary.to_dict()
        _emit("alert_updated", primary_payload)
        # Le citoyen garde SA référence et suit l'avancement de l'incident.
        return alert.to_dict()

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

    # Par défaut, on n'affiche que les incidents PRINCIPAUX : les doublons sont
    # regroupés (compteur « signalements liés » sur le principal). include_dupes
    # permet de tout lister si besoin.
    if not f.get("include_dupes"):
        query = query.filter(Alert.duplicate_of_id.is_(None))

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
