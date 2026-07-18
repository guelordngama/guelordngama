"""Endpoints des alertes : création (citoyen), consultation, affectation,
clôture (opérateur)."""
from flask import Blueprint, current_app, jsonify, request

from ..security import require_auth
from ..services import alerts as alerts_service
from ..services import stats as stats_service
from ..validation import validate_alert_payload, validate_team_id

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@bp.post("")
def create():
    data = validate_alert_payload(request.get_json(silent=True))
    payload = alerts_service.create_alert(data)
    stats_service.invalidate_cache()
    return jsonify(payload), 201


@bp.get("")
def list_():
    status = request.args.get("status")
    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(
        current_app.config["ALERTS_MAX_PAGE_SIZE"],
        request.args.get("page_size", current_app.config["ALERTS_PAGE_SIZE"], type=int),
    )
    result = alerts_service.list_alerts(status=status, page=page, page_size=page_size)
    # Compatibilité : renvoie une liste simple si aucun paramètre de pagination.
    if "page" not in request.args and "page_size" not in request.args:
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
@require_auth(roles=["operator", "admin"])
def close(alert_id):
    payload = alerts_service.close_alert(alert_id)
    stats_service.invalidate_cache()
    return jsonify(payload)
