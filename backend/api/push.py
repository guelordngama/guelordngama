"""Abonnement aux notifications push (portail des agents)."""
from flask import Blueprint, g, jsonify, request

from ..errors import ValidationError
from ..security import rate_limit, require_auth
from ..services import push as push_service

bp = Blueprint("push", __name__, url_prefix="/api/push")

_STAFF = ["agent", "operator", "supervisor", "admin"]


@bp.get("/key")
def public_key():
    """Clé publique VAPID (publique par nature)."""
    return jsonify({"key": push_service.public_key_b64()})


@bp.post("/subscribe")
@require_auth(roles=_STAFF)
@rate_limit(20, 60, scope="push_subscribe")
def subscribe():
    data = request.get_json(silent=True) or {}
    keys = data.get("keys") or {}
    endpoint, p256dh, auth = data.get("endpoint"), keys.get("p256dh"), keys.get("auth")
    if not (isinstance(endpoint, str) and endpoint.startswith("https://") and len(endpoint) < 2000
            and isinstance(p256dh, str) and isinstance(auth, str)):
        raise ValidationError("Abonnement push invalide.")
    push_service.save_subscription(g.user["uid"], endpoint, p256dh, auth)
    return jsonify({"ok": True})


@bp.post("/unsubscribe")
@require_auth(roles=_STAFF)
def unsubscribe():
    endpoint = (request.get_json(silent=True) or {}).get("endpoint")
    if isinstance(endpoint, str):
        push_service.remove_subscription(g.user["uid"], endpoint)
    return jsonify({"ok": True})
