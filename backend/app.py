"""Point d'entrée applicatif SafeCity (compatibilité + serveur de dev).

Ce module reste mince : la construction de l'application vit dans la fabrique
`backend.create_app`. Il expose `app` et `socketio` pour Waitress/Gunicorn et
permet le lancement direct (bouton Run de PyCharm) en plus de
`python -m backend.app`.
"""
import os

# Permet le lancement direct du fichier (sans contexte de package).
if __package__ in (None, ""):
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "backend"

from . import create_app, socketio  # noqa: E402

# Instance module-level pour Waitress / Gunicorn / `flask run`.
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("SAFECITY_PORT", "5000"))
    print(f"[SafeCity] Serveur de développement sur http://127.0.0.1:{port}")
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
