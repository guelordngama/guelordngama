"""Proxy de tuiles de carte.

Permet aux clients (poste opérateur, portail, site citoyen) d'afficher la carte
même lorsque le réseau local bloque les CDN de tuiles externes : c'est le
serveur SafeCity qui récupère les tuiles (fond CARTO « Voyager », style
OpenStreetMap coloré) et les met en cache sur disque, puis les sert depuis son
propre domaine — déjà autorisé par le pare-feu.

Route : GET /tiles/<z>/<x>/<y>.png
"""
import logging
import os
import urllib.request

from flask import Blueprint, Response, current_app, send_file

log = logging.getLogger("safecity")

bp = Blueprint("tiles", __name__)

# Fond CARTO Voyager (coloré, style OSM). Un seul hôte : le cache disque évite
# de solliciter le CDN à chaque requête.
_UPSTREAM = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
_UA = "SafeCity/1.0 (municipal safety platform)"


def _cache_dir():
    d = current_app.config.get("TILECACHE_DIR")
    if not d:
        d = os.path.join(current_app.config["UPLOAD_DIR"], "..", "tilecache")
    d = os.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d


@bp.get("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    # Bornes de sécurité (évite les requêtes absurdes).
    if not (0 <= z <= 20) or not (0 <= x < (1 << z)) or not (0 <= y < (1 << z)):
        return Response("bad tile", status=400)

    path = os.path.join(_cache_dir(), f"{z}_{x}_{y}.png")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        url = _UPSTREAM.format(z=z, x=x, y=y)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
            tmp = path + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
        except Exception as e:  # pragma: no cover - dépend du réseau du serveur
            log.warning("Tuile %s/%s/%s indisponible : %s", z, x, y, e)
            return Response("tile unavailable", status=502)

    resp = send_file(path, mimetype="image/png", conditional=True)
    resp.headers["Cache-Control"] = "public, max-age=2592000"  # 30 jours
    return resp
