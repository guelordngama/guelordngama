"""Notifications : e-mail (SMTP) et SMS via une passerelle adaptée à la RDC.

Passerelles SMS prises en charge (par ordre de priorité si plusieurs
configurées) :
  1. **Orange RD Congo** — API SMS officielle de l'opérateur (recommandé RDC).
  2. **Passerelle HTTP générique** — tout agrégateur/opérateur local exposant
     une API HTTP (Vodacom, Airtel, revendeurs…).
  3. **Africa's Talking** — agrégateur régional.

Aucune dépendance externe (smtplib + urllib de la bibliothèque standard).
L'envoi des notifications d'alerte est non bloquant (thread) et **optionnel** :
si aucun canal n'est configuré, la fonction ne fait rien.
"""
import base64
import json as _json
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


# --------------------------------------------------------------------------- #
# E-mail
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# SMS
# --------------------------------------------------------------------------- #
def _sms_gateway_configured(cfg):
    return bool(
        (cfg.get("ORANGE_CLIENT_ID") and cfg.get("ORANGE_CLIENT_SECRET") and cfg.get("ORANGE_SENDER"))
        or cfg.get("SMS_HTTP_URL")
        or (cfg.get("AT_USERNAME") and cfg.get("AT_API_KEY"))
    )


def sms_configured():
    """Vrai si une passerelle SMS est configurée (Orange, HTTP générique, AT)."""
    return _sms_gateway_configured(current_app.config)


def send_sms(to, text):
    """Envoie un SMS via la passerelle configurée (par priorité). Lève en cas d'échec."""
    cfg = current_app.config
    if cfg.get("ORANGE_CLIENT_ID") and cfg.get("ORANGE_CLIENT_SECRET") and cfg.get("ORANGE_SENDER"):
        _send_sms_orange(to, text, cfg)
    elif cfg.get("SMS_HTTP_URL"):
        _send_sms_http(to, text, cfg)
    elif cfg.get("AT_USERNAME") and cfg.get("AT_API_KEY"):
        _send_sms_africastalking(to, text, cfg)
    else:
        raise RuntimeError("Aucune passerelle SMS configurée.")


def _tel(number):
    """Normalise un numéro au format « tel:+243… » attendu par l'API Orange."""
    n = str(number).strip()
    if n.startswith("tel:"):
        return n
    if not n.startswith("+"):
        n = "+" + n.lstrip("+")
    return "tel:" + n


def _orange_token(cfg):
    """Obtient un jeton OAuth2 (client_credentials) auprès d'Orange."""
    creds = base64.b64encode(
        f"{cfg['ORANGE_CLIENT_ID']}:{cfg['ORANGE_CLIENT_SECRET']}".encode()).decode()
    req = urllib.request.Request(
        cfg["ORANGE_TOKEN_URL"], data=b"grant_type=client_credentials", method="POST")
    req.add_header("Authorization", "Basic " + creds)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = _json.loads(resp.read().decode("utf-8", "ignore"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Orange : jeton d'accès non obtenu.")
    return token


def _send_sms_orange(to, text, cfg):
    """Envoi d'un SMS via l'API Orange SMS (couverture RDC).

    Doc : https://developer.orange.com/apis/sms
    """
    token = _orange_token(cfg)
    sender_addr = cfg["ORANGE_SENDER"]
    url = (cfg["ORANGE_SMS_URL"].rstrip("/") + "/"
           + urllib.parse.quote(sender_addr, safe="") + "/requests")
    body = {"outboundSMSMessageRequest": {
        "address": _tel(to),
        "senderAddress": sender_addr,
        "outboundSMSTextMessage": {"message": text},
    }}
    req = urllib.request.Request(url, data=_json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def _send_sms_http(to, text, cfg):
    """Passerelle SMS HTTP générique (fournisseur local paramétrable)."""
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


def _send_sms_africastalking(to, text, cfg):
    """Envoi d'un SMS via l'API Africa's Talking (agrégateur régional).

    Doc : https://developers.africastalking.com/docs/sms/sending/bulk
    """
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


# --------------------------------------------------------------------------- #
# Notifications d'alerte (e-mail + SMS aux superviseurs)
# --------------------------------------------------------------------------- #
def dispatch_alert_notifications(alert):
    """Décide et lance l'envoi des notifications pour une alerte (non bloquant)."""
    cfg = current_app.config
    if alert.get("urgency") not in cfg["NOTIFY_URGENCY_LEVELS"]:
        return

    email_to = cfg["SMTP_TO"]
    sms_to = cfg["SMS_ALERT_TO"]
    has_email = bool(cfg.get("SMTP_HOST") and email_to)
    has_sms = bool(sms_to) and _sms_gateway_configured(cfg)
    if not has_email and not has_sms:
        return  # aucun canal configuré

    app = current_app._get_current_object()
    threading.Thread(
        target=_send_all, args=(app, alert, email_to, sms_to, has_email, has_sms), daemon=True
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


def _send_all(app, alert, email_to, sms_to, has_email, has_sms):
    with app.app_context():
        if has_email:
            try:
                send_email_message(email_to, _subject(alert), _body_text(alert))
                log.info("Notification e-mail envoyée pour l'alerte #%s", alert.get("id"))
            except Exception as e:  # pragma: no cover - dépend du réseau/SMTP
                log.warning("Échec e-mail alerte #%s : %s", alert.get("id"), e)
        if has_sms:
            text = _sms_text(alert)
            for to in sms_to:
                try:
                    send_sms(to, text)
                    log.info("Notification SMS envoyée à %s pour l'alerte #%s", to, alert.get("id"))
                except Exception as e:  # pragma: no cover
                    log.warning("Échec SMS (%s) alerte #%s : %s", to, alert.get("id"), e)
