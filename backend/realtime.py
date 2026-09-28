"""Événements temps réel Socket.IO du centre de surveillance.

Suit le nombre de clients connectés (statistiques du tableau de bord) ainsi que
la **présence par utilisateur** : chaque client s'identifie (événement
« identify ») après connexion, ce qui permet de savoir qui est en ligne pour
l'onglet « Infos » de la messagerie.
"""
import logging
import threading

from flask import current_app, request
from flask_socketio import emit, join_room

from .extensions import socketio

log = logging.getLogger("safecity")

_lock = threading.Lock()
_connected = 0
_sid_uid = {}          # session Socket.IO -> id utilisateur
_online = {}           # id utilisateur -> nombre de sessions ouvertes


def connected_count():
    with _lock:
        return _connected


def online_user_ids():
    """Ensemble des ids d'utilisateurs actuellement connectés."""
    with _lock:
        return {uid for uid, n in _online.items() if n > 0}


def _emit_presence():
    socketio.emit("presence", {"online": sorted(online_user_ids())},
                  room=current_app.config["SURVEILLANCE_ROOM"])


STAFF_ROLES = {"agent", "operator", "supervisor", "admin"}
_sid_staff = {}        # session Socket.IO -> {"uid", "role"} (personnel authentifié)


def _authenticate(auth):
    """Vérifie le jeton envoyé à la connexion (``io(url, {auth: {token}})``).

    Renvoie {"uid", "role"} pour un membre du personnel actif, sinon None.
    Aucun jeton, jeton invalide/expiré, compte désactivé ou citoyen => None.
    """
    token = auth.get("token") if isinstance(auth, dict) else None
    if not token:
        return None
    from .security import decode_token

    try:
        payload = decode_token(token)
    except Exception:
        return None
    if payload.get("role") not in STAFF_ROLES:
        return None
    from .extensions import db
    from .models import User

    user = db.session.get(User, payload.get("uid"))
    if not user or not user.active or user.role not in STAFF_ROLES:
        return None
    return {"uid": user.id, "role": user.role}


def register_socket_events():
    @socketio.on("connect")
    def on_connect(auth=None):
        """Seul le PERSONNEL authentifié rejoint la salle de surveillance, qui
        reçoit alertes (nom, téléphone, GPS des citoyens), positions des agents
        et messages. Une connexion anonyme (site citoyen) reste acceptée pour
        l'indicateur « connecté », mais ne reçoit AUCUNE donnée."""
        global _connected
        staff = _authenticate(auth)
        # Réponse à CE client uniquement (jamais de diffusion générale).
        emit("connected", {"message": "Connecté au centre SafeCity",
                           "authorized": bool(staff)})
        if not staff:
            log.debug("Connexion temps réel anonyme (aucune donnée transmise)")
            return
        join_room(current_app.config["SURVEILLANCE_ROOM"])
        with _lock:
            _sid_staff[request.sid] = staff
            _connected += 1
        socketio.emit("agents_count", {"count": connected_count()},
                      room=current_app.config["SURVEILLANCE_ROOM"])
        log.debug("Personnel connecté au temps réel (%d en ligne)", connected_count())

    @socketio.on("identify")
    def on_identify(_data=None):
        """Présence par personne. L'identité vient du JETON vérifié à la
        connexion, jamais de l'identifiant envoyé par le client (usurpation)."""
        with _lock:
            staff = _sid_staff.get(request.sid)
            if not staff or request.sid in _sid_uid:
                return
            uid = staff["uid"]
            _sid_uid[request.sid] = uid
            _online[uid] = _online.get(uid, 0) + 1
        _emit_presence()

    @socketio.on("disconnect")
    def on_disconnect(*_args):
        global _connected
        with _lock:
            staff = _sid_staff.pop(request.sid, None)
            if staff:
                _connected = max(0, _connected - 1)
            uid = _sid_uid.pop(request.sid, None)
            changed = False
            if uid is not None and uid in _online:
                _online[uid] -= 1
                if _online[uid] <= 0:
                    del _online[uid]
                changed = True
        if changed:
            _emit_presence()
        log.debug("Client temps réel déconnecté (%d en ligne)", connected_count())
