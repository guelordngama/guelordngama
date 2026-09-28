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
    alert_id = request.args.get("alert_id", type=int)
    q = (request.args.get("q") or "").strip()
    query = AuditLog.query
    if action:
        query = query.filter_by(action=action)
    if alert_id:
        query = query.filter_by(alert_id=alert_id)
    if q:
        like = f"%{q}%"
        query = query.filter(AuditLog.user_name.ilike(like) | AuditLog.detail.ilike(like)
                             | AuditLog.action.ilike(like))
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in rows])
