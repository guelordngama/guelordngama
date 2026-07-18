"""Événements temps réel Socket.IO du centre de surveillance."""
import logging

from flask import current_app
from flask_socketio import join_room

from .extensions import socketio

log = logging.getLogger("safecity")


def register_socket_events():
    @socketio.on("connect")
    def on_connect():
        # Chaque poste opérateur rejoint la salle de surveillance.
        join_room(current_app.config["SURVEILLANCE_ROOM"])
        socketio.emit("connected", {"message": "Connecté au centre SafeCity"})
        log.debug("Client temps réel connecté")

    @socketio.on("disconnect")
    def on_disconnect():
        log.debug("Client temps réel déconnecté")
