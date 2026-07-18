"""Service de suivi des agents d'intervention et analyse de performance."""
import logging
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import func

from ..extensions import db, socketio
from ..geo import haversine_m
from ..models import Alert, User

log = logging.getLogger("safecity")

OPERATIONAL_ROLES = ("agent", "operator", "supervisor", "admin")


def _emit(event, payload):
    socketio.emit(event, payload, room=current_app.config["SURVEILLANCE_ROOM"])


def list_agents(role=None, with_tracking=True):
    query = User.query.filter(User.role.in_(OPERATIONAL_ROLES))
    if role:
        query = query.filter(User.role == role)
    return [u.to_dict(with_tracking=with_tracking)
            for u in query.order_by(User.role.desc(), User.name).all()]


def update_location(agent_id, lat, lng):
    agent = db.session.get(User, agent_id)
    if not agent:
        return None
    # Accumule la distance parcourue (analytics).
    if agent.lat is not None and agent.lng is not None:
        agent.distance_total_m = (agent.distance_total_m or 0.0) + haversine_m(
            agent.lat, agent.lng, lat, lng
        )
    agent.lat, agent.lng = lat, lng
    agent.last_seen = datetime.utcnow()
    if agent.availability == "offline":
        agent.availability = "available"
    db.session.commit()
    payload = agent.to_dict(with_tracking=True)
    _emit("agent_updated", payload)
    return payload


def update_status(agent_id, availability):
    agent = db.session.get(User, agent_id)
    if not agent:
        return None
    if availability in ("available", "busy", "offline"):
        agent.availability = availability
        agent.last_seen = datetime.utcnow()
        db.session.commit()
    payload = agent.to_dict(with_tracking=True)
    _emit("agent_updated", payload)
    return payload


def performance(period="month"):
    """Statistiques de performance par agent sur la période.

    Retourne un dict global + une liste par agent : interventions, temps de
    réponse moyen (min), taux de résolution, distance parcourue (m).
    """
    now = datetime.utcnow()
    if period == "week":
        since = now - timedelta(days=7)
    elif period == "year":
        since = now - timedelta(days=365)
    else:  # month
        since = now - timedelta(days=30)

    agents = User.query.filter(User.role.in_(OPERATIONAL_ROLES)).all()
    rows = []
    for a in agents:
        handled = Alert.query.filter(
            Alert.assigned_agent_id == a.id, Alert.created_at >= since
        ).all()
        resolved = [x for x in handled if x.status == "cloturee"]
        # Temps de réponse : prise en charge - création (min).
        resp = [
            (x.accepted_at - x.created_at).total_seconds() / 60.0
            for x in handled if x.accepted_at and x.created_at
        ]
        avg_resp = round(sum(resp) / len(resp), 1) if resp else None
        rate = round(100.0 * len(resolved) / len(handled), 1) if handled else 0.0
        dist = sum(x.distance_m or 0 for x in handled)
        rows.append({
            "agent_id": a.id,
            "name": a.name,
            "role": a.role,
            "interventions": len(handled),
            "resolved": len(resolved),
            "resolution_rate": rate,
            "avg_response_min": avg_resp,
            "distance_m": round(dist, 1),
            "availability": a.availability,
        })
    rows.sort(key=lambda r: r["interventions"], reverse=True)

    total_int = sum(r["interventions"] for r in rows)
    total_res = sum(r["resolved"] for r in rows)
    all_resp = [r["avg_response_min"] for r in rows if r["avg_response_min"] is not None]
    return {
        "period": period,
        "since": since.isoformat(),
        "total_interventions": total_int,
        "total_resolved": total_res,
        "global_resolution_rate": round(100.0 * total_res / total_int, 1) if total_int else 0.0,
        "global_avg_response_min": round(sum(all_resp) / len(all_resp), 1) if all_resp else None,
        "agents": rows,
    }
