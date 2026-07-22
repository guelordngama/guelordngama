"""Endpoints des alertes : création (citoyen), consultation, affectation,
clôture (opérateur)."""
from flask import Blueprint, current_app, g, jsonify, request

from ..security import require_auth
from ..services import alerts as alerts_service
from ..services import audit
from ..services import stats as stats_service
from ..validation import validate_alert_payload, validate_team_id

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@bp.post("")
def create():
    data = validate_alert_payload(request.get_json(silent=True))
    payload = alerts_service.create_alert(data)
    stats_service.invalidate_cache()
    return jsonify(payload), 201


FILTER_KEYS = ("status", "type", "urgency", "neighborhood", "agent_id", "q",
               "date_from", "date_to")


@bp.get("")
def list_():
    filters = {k: request.args.get(k) for k in FILTER_KEYS if request.args.get(k)}
    if "agent_id" in filters:
        try:
            filters["agent_id"] = int(filters["agent_id"])
        except ValueError:
            filters.pop("agent_id")
    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(
        current_app.config["ALERTS_MAX_PAGE_SIZE"],
        request.args.get("page_size", current_app.config["ALERTS_PAGE_SIZE"], type=int),
    )
    result = alerts_service.list_alerts(filters=filters, page=page, page_size=page_size)
    # Compatibilité : liste simple si ni pagination ni filtre de recherche.
    search_keys = {"page", "page_size", "q", "type", "urgency", "neighborhood",
                   "agent_id", "date_from", "date_to"}
    if not (search_keys & set(request.args.keys())):
        return jsonify(result["items"])
    return jsonify(result)


@bp.get("/<int:alert_id>")
def detail(alert_id):
    return jsonify(alerts_service.get_alert(alert_id).to_dict())


@bp.post("/<int:alert_id>/assign")
@require_auth(roles=["operator", "admin"])
def assign(alert_id):
    team_id = validate_team_id(request.get_json(silent=True))
    payload = alerts_service.assign_team(alert_id, team_id)
    stats_service.invalidate_cache()
    return jsonify(payload)


@bp.post("/<int:alert_id>/close")
@require_auth(roles=["operator", "supervisor", "admin"])
def close(alert_id):
    payload = alerts_service.close_alert(alert_id)
    stats_service.invalidate_cache()
    audit.record("alert_closed", detail=f"alerte #{alert_id}")
    return jsonify(payload)


@bp.post("/<int:alert_id>/assign-agent")
@require_auth(roles=["operator", "supervisor", "admin"])
def assign_agent(alert_id):
    data = request.get_json(silent=True) or {}
    try:
        agent_id = int(data.get("agent_id"))
    except (TypeError, ValueError):
        from ..errors import ValidationError
        raise ValidationError("Le champ 'agent_id' (entier) est requis.")
    payload = alerts_service.assign_agent(alert_id, agent_id)
    stats_service.invalidate_cache()
    return jsonify(payload)


@bp.post("/<int:alert_id>/accept")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def accept(alert_id):
    """Prise en charge d'une intervention par l'agent connecté."""
    payload = alerts_service.accept_intervention(alert_id, g.user)
    stats_service.invalidate_cache()
    return jsonify(payload)


@bp.post("/<int:alert_id>/complete")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def complete(alert_id):
    """L'agent termine (clôture) sa propre intervention."""
    payload = alerts_service.complete_intervention(alert_id, g.user)
    stats_service.invalidate_cache()
    return jsonify(payload)
