"""Gestion des agents / opérateurs (lecture)."""
from flask import Blueprint, jsonify, request

from ..models import ROLES, User
from ..security import require_auth

bp = Blueprint("agents", __name__, url_prefix="/api")


@bp.get("/agents")
@require_auth(roles=["operator", "supervisor", "admin"])
def list_agents():
    """Liste les personnels (agents, opérateurs, superviseurs, admins)."""
    role = request.args.get("role")
    query = User.query.filter(User.role != "citizen")
    if role in ROLES:
        query = query.filter_by(role=role)
    users = query.order_by(User.role.desc(), User.name).all()
    return jsonify([u.to_dict() for u in users])


@bp.get("/citizens")
@require_auth(roles=["operator", "supervisor", "admin"])
def list_citizens():
    """Liste les citoyens enregistrés."""
    users = User.query.filter_by(role="citizen").order_by(User.created_at.desc()).limit(500).all()
    return jsonify([u.to_dict() for u in users])
