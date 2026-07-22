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


def sms_configured():
    """Vrai si une passerelle SMS est configurée (Africa's Talking, HTTP, Twilio)."""
    cfg = current_app.config
    return bool(
        (cfg.get("AT_USERNAME") and cfg.get("AT_API_KEY"))
        or cfg.get("SMS_HTTP_URL")
        or (cfg.get("TWILIO_SID") and cfg.get("TWILIO_FROM"))
    )


def send_sms(to, text):
    """Envoie un SMS à un destinataire via la passerelle configurée. Lève en cas d'échec."""
    cfg = current_app.config
    if cfg.get("AT_USERNAME") and cfg.get("AT_API_KEY"):
        _send_sms_africastalking(to, text, cfg)
    elif cfg.get("SMS_HTTP_URL"):
        _send_sms_http(to, text, cfg)
    elif cfg.get("TWILIO_SID") and cfg.get("TWILIO_FROM"):
        _send_sms_twilio(to, text, cfg)
    else:
        raise RuntimeError("Aucune passerelle SMS configurée.")


def _send_sms_africastalking(to, text, cfg):
    """Envoi d'un SMS via l'API Africa's Talking (couverture RDC).

    Doc : https://developers.africastalking.com/docs/sms/sending/bulk
    """
    import json as _json

    username = cfg["AT_USERNAME"]
    sandbox = cfg.get("AT_SANDBOX") or username == "sandbox"
    base = "https://api.sandbox.africastalking.com" if sandbox else "https://api.africastalking.com"
    url = base + "/version1/messaging"

    params = {"username": username, "to": to, "message": text}
    if cfg.get("AT_SENDER"):
        params["from"] = cfg["AT_SENDER"]

    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(params).encode(), method="POST")
    req.add_header("apiKey", cfg["AT_API_KEY"])
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8", "ignore")

    # Vérifie le statut de livraison (101=Sent, 100=Processed, 102=Queued = OK).
    try:
        recipients = _json.loads(body).get("SMSMessageData", {}).get("Recipients", [])
    except ValueError:
        recipients = []
    if recipients and recipients[0].get("statusCode") not in (100, 101, 102):
        raise RuntimeError(
            f"Africa's Talking a refusé l'envoi : {recipients[0].get('status')}")


def _send_sms_http(to, text, cfg):
    """Passerelle SMS HTTP générique (fournisseur local paramétrable)."""
    import json as _json

    params = {cfg["SMS_HTTP_TO_PARAM"]: to, cfg["SMS_HTTP_TEXT_PARAM"]: text}
    for pair in (cfg.get("SMS_HTTP_EXTRA") or "").split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k.strip()] = v.strip()
    headers = {}
    if cfg.get("SMS_HTTP_AUTH_HEADER"):
        headers["Authorization"] = cfg["SMS_HTTP_AUTH_HEADER"]

    url = cfg["SMS_HTTP_URL"]
    method = (cfg.get("SMS_HTTP_METHOD") or "POST").upper()
    if method == "GET":
        full = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(full, headers=headers, method="GET")
    elif cfg.get("SMS_HTTP_JSON"):
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, data=_json.dumps(params).encode(), headers=headers, method="POST")
    else:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(params).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def _send_sms_twilio(to, text, cfg):
    """Envoi d'un SMS unique via l'API Twilio."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['TWILIO_SID']}/Messages.json"
    data = urllib.parse.urlencode({"From": cfg["TWILIO_FROM"], "To": to, "Body": text}).encode()
    auth = base64.b64encode(f"{cfg['TWILIO_SID']}:{cfg['TWILIO_TOKEN']}".encode()).decode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


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
