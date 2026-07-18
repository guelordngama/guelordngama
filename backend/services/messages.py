"""Messagerie temps réel entre opérateurs et agents."""
import logging

from flask import current_app

from ..extensions import db, socketio
from ..models import Message

log = logging.getLogger("safecity")


def create_message(sender, text, alert_id=None):
    """Enregistre et diffuse un message. `sender` est le payload JWT (g.user)."""
    msg = Message(
        sender_id=sender.get("uid"),
        sender_name=sender.get("name") or "Inconnu",
        sender_role=sender.get("role"),
        text=text,
        alert_id=alert_id,
    )
    db.session.add(msg)
    db.session.commit()
    payload = msg.to_dict()
    socketio.emit("chat_message", payload, room=current_app.config["SURVEILLANCE_ROOM"])
    log.debug("Message de %s : %s", msg.sender_name, (text or "")[:40])
    return payload


def list_messages(limit=50, alert_id=None):
    query = Message.query
    if alert_id:
        query = query.filter(Message.alert_id == alert_id)
    msgs = query.order_by(Message.created_at.desc()).limit(limit).all()
    return [m.to_dict() for m in reversed(msgs)]  # ordre chronologique
