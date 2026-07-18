"""Endpoints de service : santé et métadonnées."""
from datetime import datetime

from flask import Blueprint, jsonify

from ..models import ALERT_STATUSES, DANGER_TYPES

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@bp.get("/meta")
def meta():
    """Métadonnées utiles au front (types de danger, statuts)."""
    return jsonify({"danger_types": DANGER_TYPES, "statuses": ALERT_STATUSES})
