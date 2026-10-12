"""Messagerie citoyen ↔ centre (opérateurs) rattachée à une alerte.

Le citoyen s'identifie par la référence publique de SON alerte (non devinable,
comme pour le suivi de position). Messages courts (500 caractères).
"""
import logging
from datetime import datetime

from flask import current_app

from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db, socketio
from ..models import Alert, AlertMessage

log = logging.getLogger("safecity")
MAX_LEN = 500


def _clean(text):
    text = " ".join((text or "").split()) if isinstance(text, str) else ""
    if not text:
        raise ValidationError("Le message est vide.")
    if len(text) > MAX_LEN:
        raise ValidationError(f"Message trop long ({MAX_LEN} caractères maximum).")
    return text


def _by_ref(reference):
    alert = Alert.query.filter_by(public_ref=(reference or "").strip().upper()).first()
    if not alert:
        raise NotFoundError("Référence introuvable.")
    return alert


def _shown(alert):
    """Incident affiché au centre : l'alerte principale si c'est un doublon."""
    return alert.primary if (alert.duplicate_of_id and alert.primary) else alert


def list_for_citizen(reference, after=0):
    alert = _by_ref(reference)
    q = AlertMessage.query.filter_by(alert_id=alert.id).order_by(AlertMessage.id)
    if after:
        q = q.filter(AlertMessage.id > after)
    return [m.to_dict(alert.public_ref) for m in q.all()]


def post_from_citizen(reference, text):
    text = _clean(text)
    alert = _by_ref(reference)
    if alert.status == "cloturee" or alert.false_alarm or alert.cancelled_by_citizen:
        raise ConflictError("Cette alerte est clôturée : la messagerie est terminée.",
                            details={"closed": True})
    msg = AlertMessage(alert_id=alert.id, sender="citizen", text=text,
                       sender_name=(alert.reporter_name or "Citoyen")[:120])
    shown = _shown(alert)
    shown.citizen_msg_unread = (shown.citizen_msg_unread or 0) + 1
    db.session.add(msg)
    db.session.commit()
    data = msg.to_dict(alert.public_ref)
    data["incident_id"] = shown.id
    socketio.emit("citizen_message", data, room=current_app.config["OPERATORS_ROOM"])
    _emit_updated(shown)
    return data


def _emit_updated(shown):
    from .alerts import _emit, attach_reporter_flags

    _emit("alert_updated", attach_reporter_flags([shown.to_dict()])[0])


def _family_ids(incident):
    """Alerte + doublons rattachés (plusieurs citoyens, un même incident)."""
    ids = [incident.id] + [a.id for a in Alert.query.filter_by(duplicate_of_id=incident.id).all()]
    refs = {a.id: a.public_ref for a in Alert.query.filter(Alert.id.in_(ids)).all()}
    return ids, refs


def list_for_operator(alert_id):
    """Fil complet de l'incident ; marque les messages comme lus."""
    incident = db.session.get(Alert, alert_id)
    if not incident:
        raise NotFoundError("Alerte introuvable.")
    ids, refs = _family_ids(incident)
    msgs = (AlertMessage.query.filter(AlertMessage.alert_id.in_(ids))
            .order_by(AlertMessage.id).all())
    if incident.citizen_msg_unread:
        incident.citizen_msg_unread = 0
        db.session.commit()
        _emit_updated(incident)
    return [m.to_dict(refs.get(m.alert_id)) for m in msgs]


def post_from_operator(alert_id, text, by_name, reference=None):
    text = _clean(text)
    incident = db.session.get(Alert, alert_id)
    if not incident:
        raise NotFoundError("Alerte introuvable.")
    ids, refs = _family_ids(incident)
    target_id = incident.id
    if reference:
        match = [i for i, r in refs.items() if r == reference.strip().upper()]
        if not match:
            raise ValidationError("Référence étrangère à cet incident.")
        target_id = match[0]
    target = db.session.get(Alert, target_id)
    if target.cancelled_by_citizen:
        raise ConflictError("Le citoyen a annulé cette alerte.", details={"closed": True})
    msg = AlertMessage(alert_id=target.id, sender="operator", text=text,
                       sender_name=(by_name or "Centre SafeCity")[:120])
    if incident.citizen_msg_unread:
        incident.citizen_msg_unread = 0
    db.session.add(msg)
    db.session.commit()
    return msg.to_dict(target.public_ref)
