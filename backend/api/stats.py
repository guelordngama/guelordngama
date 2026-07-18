"""Endpoint des statistiques du tableau de bord."""
from flask import Blueprint, jsonify

from ..services import stats as stats_service

bp = Blueprint("stats", __name__, url_prefix="/api")


@bp.get("/stats")
def stats():
    return jsonify(stats_service.compute_stats())
