"""Notifications push à l'arrivée d'une alerte : e-mail (SMTP) et SMS (Twilio).

Non bloquant (envoi dans un thread) et **optionnel** : si aucun canal n'est
configuré, la fonction ne fait rien. Aucune dépendance externe (smtplib +
urllib de la bibliothèque standard).
"""
import base64
import logging
import smtplib
import ssl
import threading
import urllib.parse
import urllib.request
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger("safecity")

URGENCY_LABELS = {"faible": "Faible", "moyenne": "Moyen", "haute": "Élevé", "critique": "Critique"}


def smtp_configured():
    """Vrai si un serveur SMTP est configuré (envoi d'e-mail possible)."""
    return bool(current_app.config.get("SMTP_HOST"))


def send_email_message(to_addrs, subject, body):
    """Envoie un e-mail simple (texte) via le SMTP configuré. Lève en cas d'échec."""
    cfg = current_app.config
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(body)

    with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as server:
        if cfg["SMTP_TLS"]:
            server.starttls(context=ssl.create_default_context())
        if cfg["SMTP_USER"]:
            server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
        server.send_message(msg)


def dispatch_alert_notifications(alert):
    """Décide et lance l'envoi des notifications pour une alerte (non bloquant)."""
    cfg = current_app.config
    if alert.get("urgency") not in cfg["NOTIFY_URGENCY_LEVELS"]:
        return

    email_cfg = {
        "host": cfg["SMTP_HOST"], "port": cfg["SMTP_PORT"], "user": cfg["SMTP_USER"],
        "password": cfg["SMTP_PASSWORD"], "sender": cfg["SMTP_FROM"], "tls": cfg["SMTP_TLS"],
        "to": cfg["SMTP_TO"],
    }
    sms_cfg = {
        "sid": cfg["TWILIO_SID"], "token": cfg["TWILIO_TOKEN"],
        "sender": cfg["TWILIO_FROM"], "to": cfg["TWILIO_TO"],
    }
    if not (email_cfg["host"] and email_cfg["to"]) and not (sms_cfg["sid"] and sms_cfg["to"]):
        return  # aucun canal configuré

    threading.Thread(
        target=_send_all, args=(alert, email_cfg, sms_cfg), daemon=True
    ).start()


def _subject(alert):
    return f"[SafeCity] Alerte {URGENCY_LABELS.get(alert.get('urgency'), '')} — {alert.get('type', '').capitalize()}"


def _body_text(alert):
    return (
        "Nouvelle alerte SafeCity\n\n"
        f"Type       : {alert.get('type', '').capitalize()}\n"
        f"Urgence    : {URGENCY_LABELS.get(alert.get('urgency'), alert.get('urgency'))}\n"
        f"Quartier   : {alert.get('neighborhood') or '—'}\n"
        f"Position   : {alert.get('lat')}, {alert.get('lng')}\n"
        f"Citoyen    : {alert.get('reporter_name') or 'Anonyme'} ({alert.get('reporter_phone') or '—'})\n"
        f"Heure      : {alert.get('time') or '—'}\n"
        f"Distance   : {alert.get('distance_m')} m\n\n"
        f"Description : {alert.get('description') or '—'}\n\n"
        f"Carte : https://www.openstreetmap.org/?mlat={alert.get('lat')}&mlon={alert.get('lng')}#map=17/{alert.get('lat')}/{alert.get('lng')}\n"
    )


def _sms_text(alert):
    return (
        f"SafeCity {URGENCY_LABELS.get(alert.get('urgency'), '')}: "
        f"{alert.get('type', '').capitalize()} à {alert.get('neighborhood') or '?'} "
        f"({alert.get('lat')},{alert.get('lng')})"
    )[:300]


def _send_all(alert, email_cfg, sms_cfg):
    if email_cfg["host"] and email_cfg["to"]:
        try:
            _send_email(alert, email_cfg)
            log.info("Notification e-mail envoyée pour l'alerte #%s", alert.get("id"))
        except Exception as e:  # pragma: no cover - dépend du réseau/SMTP
            log.warning("Échec e-mail alerte #%s : %s", alert.get("id"), e)
    if sms_cfg["sid"] and sms_cfg["to"]:
        try:
            _send_sms(alert, sms_cfg)
            log.info("Notification SMS envoyée pour l'alerte #%s", alert.get("id"))
        except Exception as e:  # pragma: no cover
            log.warning("Échec SMS alerte #%s : %s", alert.get("id"), e)


def _send_email(alert, cfg):
    msg = EmailMessage()
    msg["Subject"] = _subject(alert)
    msg["From"] = cfg["sender"]
    msg["To"] = ", ".join(cfg["to"])
    msg.set_content(_body_text(alert))

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
        if cfg["tls"]:
            server.starttls(context=ssl.create_default_context())
        if cfg["user"]:
            server.login(cfg["user"], cfg["password"])
        server.send_message(msg)


def _send_sms(alert, cfg):
    """Envoi SMS via l'API REST Twilio (sans dépendance)."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['sid']}/Messages.json"
    auth = base64.b64encode(f"{cfg['sid']}:{cfg['token']}".encode()).decode()
    for to in cfg["to"]:
        data = urllib.parse.urlencode({
            "From": cfg["sender"], "To": to, "Body": _sms_text(alert),
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", "Basic " + auth)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        urllib.request.urlopen(req, timeout=15).read()
