"""Instances d'extensions partagées (initialisées dans la factory create_app).

Centraliser les extensions ici évite les imports circulaires : les modules
(models, services, blueprints) importent depuis `backend.extensions` sans
dépendre de l'application elle-même.
"""
import os

from flask_cors import CORS
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Base de données (ORM).
db = SQLAlchemy()

# CORS (origines restreintes via la configuration).
cors = CORS()

# Temps réel. `threading` fonctionne partout sans dépendance native ; on peut
# basculer sur eventlet/gevent en production via SAFECITY_ASYNC_MODE.
socketio = SocketIO(async_mode=os.environ.get("SAFECITY_ASYNC_MODE", "threading"))
