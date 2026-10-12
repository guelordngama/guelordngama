"""Notifications Web Push (VAPID, RFC 8030 / 8291 / 8292).

Permet de prévenir un agent d'une affectation même quand son portail est
fermé ou son écran verrouillé. Implémentation autonome (cryptography + PyJWT,
déjà dépendances du projet) : aucune bibliothèque supplémentaire.

Clés VAPID : SAFECITY_VAPID_PRIVATE_KEY (PEM) si définie, sinon dérivées de
façon déterministe de la clé secrète de l'application — elles restent donc les
mêmes d'un redémarrage à l'autre (les abonnements ne sont pas perdus).
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import current_app

from ..extensions import db
from ..models import PushSubscription

log = logging.getLogger("safecity")


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _private_key():
    pem = current_app.config.get("VAPID_PRIVATE_KEY")
    if pem:
        return serialization.load_pem_private_key(pem.replace("\\n", "\n").encode(), None)
    seed = hmac.new(current_app.config["SECRET_KEY"].encode(), b"safecity-vapid-v1",
                    hashlib.sha256).digest()
    order = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
    return ec.derive_private_key(int.from_bytes(seed, "big") % (order - 1) + 1, ec.SECP256R1())


def public_key_b64():
    """Clé publique VAPID (format attendu par pushManager.subscribe)."""
    raw = _private_key().public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64(raw)


def _vapid_headers(endpoint):
    u = urllib.parse.urlparse(endpoint)
    claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600,
              "sub": current_app.config.get("VAPID_SUBJECT") or "mailto:contact@safecity.local"}
    token = jwt.encode(claims, _private_key(), algorithm="ES256")
    return {"Authorization": f"vapid t={token}, k={public_key_b64()}"}


def encrypt(payload: bytes, p256dh_b64, auth_b64):
    """Chiffrement du message (aes128gcm, RFC 8291)."""
    ua_pub_raw = _unb64(p256dh_b64)
    auth = _unb64(auth_b64)
    ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub_raw)
    as_priv = ec.generate_private_key(ec.SECP256R1())
    as_pub_raw = as_priv.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    secret = as_priv.exchange(ec.ECDH(), ua_pub)
    prk = HKDF(hashes.SHA256(), 32, auth,
               b"WebPush: info\x00" + ua_pub_raw + as_pub_raw).derive(secret)
    salt = os.urandom(16)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\x00").derive(prk)
    cipher = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + (4096).to_bytes(4, "big") + bytes([len(as_pub_raw)]) + as_pub_raw + cipher


def _send_one(sub, body):
    """Envoie au service push du navigateur. Renvoie le code HTTP (0 = réseau)."""
    data = encrypt(body, sub["p256dh"], sub["auth"])
    headers = {"Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
               "TTL": "3600", "Urgency": "high", **_vapid_headers(sub["endpoint"])}
    req = urllib.request.Request(sub["endpoint"], data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # réseau indisponible
        log.warning("Push : envoi impossible (%s)", e)
        return 0


def save_subscription(user_id, endpoint, p256dh, auth):
    """Enregistre (ou rattache à cet utilisateur) l'abonnement d'un appareil."""
    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub is None:
        sub = PushSubscription(endpoint=endpoint, p256dh=p256dh, auth=auth, user_id=user_id)
        db.session.add(sub)
    else:  # appareil partagé : l'abonnement suit l'agent connecté
        sub.user_id, sub.p256dh, sub.auth = user_id, p256dh, auth
    db.session.commit()


def remove_subscription(user_id, endpoint):
    PushSubscription.query.filter_by(endpoint=endpoint, user_id=user_id).delete()
    db.session.commit()


def notify_user(user_id, title, body, url="/portal/", tag=None):
    """Envoie une notification push à tous les appareils d'un utilisateur.

    Non bloquant (thread) ; les abonnements expirés (404/410) sont supprimés.
    """
    subs = [{"id": s.id, "endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth}
            for s in PushSubscription.query.filter_by(user_id=user_id).all()]
    if not subs:
        return 0
    app = current_app._get_current_object()
    msg = json.dumps({"title": title, "body": body, "url": url, "tag": tag}).encode()

    def run():
        with app.app_context():
            for sub in subs:
                code = _send_one(sub, msg)
                if code in (404, 410):
                    PushSubscription.query.filter_by(id=sub["id"]).delete()
                    db.session.commit()
                elif code and code >= 400:
                    log.warning("Push refusé (HTTP %s) pour l'abonnement %s", code, sub["id"])

    if app.config.get("TESTING"):
        run()
    else:
        threading.Thread(target=run, daemon=True).start()
    return len(subs)
