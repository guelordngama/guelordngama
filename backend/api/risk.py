"""Zones à risque : carte de chaleur et bilan par commune (personnel du centre)."""
from flask import Blueprint, jsonify, request

from ..models import DANGER_TYPES
from ..security import require_auth
from ..services import risk as risk_service

bp = Blueprint("risk", __name__, url_prefix="/api/risk")

# Données agrégées de positions : réservées au centre (pas aux agents de terrain).
_STAFF = ["operator", "supervisor", "admin"]


@bp.get("/heatmap")
@require_auth(roles=_STAFF)
def heatmap():
    type_ = request.args.get("type")
    band = request.args.get("band")
    return jsonify(risk_service.heatmap(
        request.args.get("days", 30),
        type_ if type_ in DANGER_TYPES else None,
        band if band in risk_service.BAND_LABELS else None))


@bp.get("/communes")
@require_auth(roles=_STAFF)
def communes():
    type_ = request.args.get("type")
    return jsonify(risk_service.communes_report(
        request.args.get("days", 30), type_ if type_ in DANGER_TYPES else None))
