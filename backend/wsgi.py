"""Point d'entrée WSGI de production (Gunicorn + worker eventlet).

Fournit de **vraies websockets** pour Socket.IO. Lancement :

    gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 backend.wsgi:app

Le `monkey_patch()` d'eventlet doit intervenir avant tout import réseau, d'où
ce module dédié et minimal.
"""
import os

os.environ.setdefault("SAFECITY_ASYNC_MODE", "eventlet")

import eventlet  # noqa: E402

eventlet.monkey_patch()

from backend import create_app, socketio  # noqa: E402,F401

app = create_app()
