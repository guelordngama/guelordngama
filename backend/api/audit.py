"""Consultation du journal d'audit (réservé aux administrateurs/superviseurs)."""
from flask import Blueprint, jsonify, request

from ..models import AuditLog
from ..security import require_auth

bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@bp.get("")
@require_auth(roles=["supervisor", "admin"])
def list_audit():
    """Dernières entrées du journal d'audit (par défaut 100, max 500)."""
    limit = min(500, max(1, request.args.get("limit", 100, type=int)))
    action = request.args.get("action")
    query = AuditLog.query
    if action:
        query = query.filter_by(action=action)
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in rows])
