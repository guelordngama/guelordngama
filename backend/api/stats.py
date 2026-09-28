"""Endpoint des statistiques du tableau de bord."""
from flask import Blueprint, jsonify

from ..security import require_auth
from ..services import stats as stats_service

bp = Blueprint("stats", __name__, url_prefix="/api")


@bp.get("/stats")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def stats():
    return jsonify(stats_service.compute_stats())
