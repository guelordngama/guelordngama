"""Agents d'intervention : liste, suivi temps réel, analyse de performance."""
from flask import Blueprint, g, jsonify, request

from ..errors import ValidationError
from ..models import ROLES, User
from ..security import require_auth
from ..services import agents as agents_service
from ..validation import coerce_float, validate_agent_payload

bp = Blueprint("agents", __name__, url_prefix="/api")


@bp.get("/agents")
@require_auth(roles=["operator", "supervisor", "admin"])
def list_agents():
    role = request.args.get("role")
    role = role if role in ROLES else None
    return jsonify(agents_service.list_agents(role=role, with_tracking=True))


@bp.post("/agents")
@require_auth(roles=["operator", "supervisor", "admin"])
def create_agent():
    data = validate_agent_payload(request.get_json(silent=True), partial=False)
    return jsonify(agents_service.create_agent(data)), 201


@bp.route("/agents/<int:agent_id>", methods=["PUT", "PATCH"])
@require_auth(roles=["operator", "supervisor", "admin"])
def update_agent(agent_id):
    data = validate_agent_payload(request.get_json(silent=True), partial=True)
    return jsonify(agents_service.update_agent(agent_id, data))


@bp.delete("/agents/<int:agent_id>")
@require_auth(roles=["operator", "supervisor", "admin"])
def delete_agent(agent_id):
    from flask import g

    return jsonify(agents_service.delete_agent(agent_id, requester_id=g.user.get("uid")))


@bp.get("/citizens")
@require_auth(roles=["operator", "supervisor", "admin"])
def list_citizens():
    users = User.query.filter_by(role="citizen").order_by(User.created_at.desc()).limit(500).all()
    return jsonify([u.to_dict() for u in users])


@bp.get("/agents/me")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def me():
    user = User.query.get(g.user["uid"])
    if not user:
        return jsonify({"error": {"message": "Introuvable"}}), 404
    return jsonify(user.to_dict(with_tracking=True))


@bp.post("/agents/me/location")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def update_location():
    data = request.get_json(silent=True) or {}
    lat = coerce_float(data.get("lat"), "lat")
    lng = coerce_float(data.get("lng"), "lng")
    payload = agents_service.update_location(g.user["uid"], lat, lng)
    if payload is None:
        raise ValidationError("Agent introuvable.")
    return jsonify(payload)


@bp.post("/agents/me/status")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def update_status():
    data = request.get_json(silent=True) or {}
    availability = (data.get("availability") or "").strip().lower()
    if availability not in ("available", "busy", "offline"):
        raise ValidationError("availability doit être available|busy|offline.")
    payload = agents_service.update_status(g.user["uid"], availability)
    return jsonify(payload)


@bp.get("/analytics")
@require_auth(roles=["supervisor", "admin", "operator"])
def analytics():
    period = request.args.get("period", "month")
    if period not in ("week", "month", "year"):
        period = "month"
    return jsonify(agents_service.performance(period))
