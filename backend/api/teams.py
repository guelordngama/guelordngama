"""Endpoints des équipes d'intervention."""
from flask import Blueprint, jsonify

from ..models import Team

bp = Blueprint("teams", __name__, url_prefix="/api/teams")


@bp.get("")
def list_():
    return jsonify([t.to_dict() for t in Team.query.order_by(Team.id).all()])
