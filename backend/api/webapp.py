"""Sert les applications front en développement (même origine que l'API).

But : en local, ouvrir simplement http://localhost:5000/ affiche l'app
citoyenne et http://localhost:5000/portal/ le portail agents. Comme la page et
l'API partagent alors la **même origine**, il n'y a aucun souci de CORS ni de
communication entre deux serveurs/ports.

En production, c'est **Nginx** qui sert ces fichiers (voir docker-compose.prod) ;
ces routes ne sont donc actives qu'en développement.
"""
import os

from flask import Blueprint, abort, send_from_directory

# Racine du dépôt (ce fichier est dans backend/api/).
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB_DIR = os.path.join(_ROOT, "web")
PORTAL_DIR = os.path.join(_ROOT, "portal")

# Préfixes réservés aux autres blueprints : le catch-all ne doit pas les servir.
_RESERVED = ("api/", "uploads/", "socket.io/", "portal/")

bp = Blueprint("frontend", __name__)


@bp.get("/")
def citizen_index():
    return send_from_directory(WEB_DIR, "index.html")


@bp.get("/portal/")
def portal_index():
    return send_from_directory(PORTAL_DIR, "index.html")


@bp.get("/portal/<path:filename>")
def portal_static(filename):
    return send_from_directory(PORTAL_DIR, filename)


@bp.get("/<path:filename>")
def citizen_static(filename):
    # Laisse l'API, les uploads, Socket.IO et le portail à leurs blueprints.
    if filename.startswith(_RESERVED):
        abort(404)
    return send_from_directory(WEB_DIR, filename)
