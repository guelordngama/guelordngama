"""Endpoints des équipes d'intervention."""
from flask import Blueprint, jsonify

from ..models import Team
from ..security import require_auth

bp = Blueprint("teams", __name__, url_prefix="/api/teams")


@bp.get("")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])   # positions des patrouilles : personnel uniquement
def list_():
    return jsonify([t.to_dict() for t in Team.query.order_by(Team.id).all()])
