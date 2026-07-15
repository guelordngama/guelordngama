"""Point d'entrée de production SafeCity.

Deux modes :
  - Waitress (par défaut) : robuste sous Windows, compatible PyInstaller.
    Le transport Socket.IO utilise le "long-polling" (fonctionne partout).
  - socketio.run : à privilégier si eventlet/gevent est installé pour de
    vraies websockets (SAFECITY_ASYNC_MODE=eventlet).

Usage :
    python -m backend.server
    # ou
    SAFECITY_SERVER=socketio python -m backend.server
"""
import os

from .app import app, socketio

HOST = os.environ.get("SAFECITY_HOST", "0.0.0.0")
PORT = int(os.environ.get("SAFECITY_PORT", "5000"))


def main():
    mode = os.environ.get("SAFECITY_SERVER", "waitress").lower()
    if mode == "socketio":
        socketio.run(app, host=HOST, port=PORT, allow_unsafe_werkzeug=True)
    else:
        from waitress import serve

        print(f"[SafeCity] Waitress en écoute sur http://{HOST}:{PORT}")
        serve(app, host=HOST, port=PORT, threads=8)


if __name__ == "__main__":
    main()
