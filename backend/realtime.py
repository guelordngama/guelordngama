"""Événements temps réel Socket.IO du centre de surveillance.

Suit également le nombre de clients (postes opérateurs / agents) connectés,
exposé dans les statistiques du tableau de bord.
"""
import logging
import threading

from flask import current_app
from flask_socketio import join_room

from .extensions import socketio

log = logging.getLogger("safecity")

_lock = threading.Lock()
_connected = 0


def connected_count():
    with _lock:
        return _connected


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

    @socketio.on("disconnect")
    def on_disconnect():
        global _connected
        with _lock:
            _connected = max(0, _connected - 1)
        log.debug("Client temps réel déconnecté (%d en ligne)", connected_count())
