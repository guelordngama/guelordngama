"""Point d'entrée de production SafeCity.

Modes disponibles (variable SAFECITY_SERVER) :
  - waitress (défaut) : robuste, compatible Windows/PyInstaller. Socket.IO en
    long-polling.
  - socketio          : serveur intégré (eventlet/gevent requis pour de vraies
    websockets ; définir SAFECITY_ASYNC_MODE=eventlet).

Usage :
    python -m backend.server
    SAFECITY_SERVER=socketio python -m backend.server
"""
import os

# Permet le lancement direct (bouton Run) en plus de `python -m backend.server`.
if __package__ in (None, ""):
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "backend"

from . import create_app, socketio  # noqa: E402

app = create_app()

HOST = os.environ.get("SAFECITY_HOST", "0.0.0.0")
PORT = int(os.environ.get("SAFECITY_PORT", "5000"))


def main():
    mode = os.environ.get("SAFECITY_SERVER", "waitress").lower()
    if mode == "socketio":
        socketio.run(app, host=HOST, port=PORT, allow_unsafe_werkzeug=True)
    else:
        from waitress import serve

        print(f"[SafeCity] Waitress en écoute sur http://{HOST}:{PORT}")
        serve(app, host=HOST, port=PORT, threads=int(os.environ.get("SAFECITY_THREADS", "12")))


if __name__ == "__main__":
    main()
