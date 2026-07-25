"""Endpoints de la messagerie temps réel."""
from flask import Blueprint, g, jsonify, request

from ..errors import ValidationError
from ..security import require_auth
from ..services import messages as messages_service
from ..validation import clean_text

bp = Blueprint("messages", __name__, url_prefix="/api/messages")

STAFF = ["agent", "operator", "supervisor", "admin"]


@bp.get("")
@require_auth(roles=STAFF)
def list_messages():
    limit = min(200, request.args.get("limit", 50, type=int))
    alert_id = request.args.get("alert_id", type=int)
    return jsonify(messages_service.list_messages(limit=limit, alert_id=alert_id))


@bp.post("")
@require_auth(roles=STAFF)
def post_message():
    data = request.get_json(silent=True) or {}
    text = clean_text(data.get("text"), 1000)
    attachment = data.get("attachment")
    voice = data.get("voice")
    video = data.get("video")
    if not text and not attachment and not voice and not video:
        raise ValidationError("Le message ne peut pas être vide.")
    duration = data.get("voice_duration")
    try:
        duration = max(0, min(7200, int(duration))) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    result = messages_service.create_message(
        g.user, text, data.get("alert_id"), attachment=attachment, voice=voice,
        voice_duration=duration, video=video)
    return jsonify(result), 201
