"""Messagerie temps réel entre opérateurs et agents."""
import logging
from datetime import datetime

from flask import current_app

from ..extensions import db, socketio
from ..models import Message, User

log = logging.getLogger("safecity")


def _iso(dt):
    return dt.isoformat() if dt else None


def _seen_pairs():
    """Liste (user_id, messages_seen_at) des utilisateurs ayant ouvert la messagerie."""
    return db.session.query(User.id, User.messages_seen_at).filter(
        User.messages_seen_at.isnot(None)).all()


def create_message(sender, text, alert_id=None, attachment=None, voice=None,
                   voice_duration=None, video=None):
    """Enregistre et diffuse un message. `sender` est le payload JWT (g.user)."""
    from ..security import save_data_url

    attachment_path = save_data_url(attachment, "image") if attachment else None
    voice_path = save_data_url(voice, "audio") if voice else None
    video_path = save_data_url(video, "video") if video else None
    msg = Message(
        sender_id=sender.get("uid"),
        sender_name=sender.get("name") or "Inconnu",
        sender_role=sender.get("role"),
        text=text,
        alert_id=alert_id,
        attachment_path=attachment_path,
        voice_path=voice_path,
        voice_duration=voice_duration if voice_path else None,
        video_path=video_path,
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
    seen = _seen_pairs()  # (user_id, seen_at)
    out = []
    for m in reversed(msgs):  # ordre chronologique
        d = m.to_dict()
        # « lu » si un AUTRE participant a ouvert la messagerie après ce message.
        d["read"] = any(
            uid != m.sender_id and s and m.created_at and s >= m.created_at
            for uid, s in seen)
        out.append(d)
    return out


def mark_read(user):
    """Marque la messagerie comme « lue » par `user` (payload JWT) et diffuse
    l'accusé de lecture aux autres participants."""
    uid = user.get("uid")
    u = User.query.get(uid) if uid else None
    if not u:
        return None
    now = datetime.utcnow()
    u.messages_seen_at = now
    db.session.commit()
    payload = {"reader_id": uid, "reader_name": u.name, "seen_at": _iso(now)}
    socketio.emit("messages_read", payload, room=current_app.config["SURVEILLANCE_ROOM"])
    return payload
