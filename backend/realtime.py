"""Événements temps réel Socket.IO du centre de surveillance.

Suit le nombre de clients connectés (statistiques du tableau de bord) ainsi que
la **présence par utilisateur** : chaque client s'identifie (événement
« identify ») après connexion, ce qui permet de savoir qui est en ligne pour
l'onglet « Infos » de la messagerie.
"""
import logging
import threading

from flask import current_app, request
from flask_socketio import join_room

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


def register_socket_events():
    @socketio.on("connect")
    def on_connect():
        global _connected
        join_room(current_app.config["SURVEILLANCE_ROOM"])
        with _lock:
            _connected += 1
        socketio.emit("connected", {"message": "Connecté au centre SafeCity"})
        socketio.emit("agents_count", {"count": connected_count()},
                      room=current_app.config["SURVEILLANCE_ROOM"])
        log.debug("Client temps réel connecté (%d en ligne)", connected_count())

    @socketio.on("identify")
    def on_identify(data):
        """Associe la session à un utilisateur (présence par personne)."""
        uid = (data or {}).get("uid")
        if not uid:
            return
        with _lock:
            _sid_uid[request.sid] = uid
            _online[uid] = _online.get(uid, 0) + 1
        _emit_presence()

    @socketio.on("disconnect")
    def on_disconnect():
        global _connected
        with _lock:
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
