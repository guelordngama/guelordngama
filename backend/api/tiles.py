"""Proxy de tuiles de carte.

Permet aux clients (poste opérateur, portail, site citoyen) d'afficher la carte
même lorsque le réseau local bloque les CDN de tuiles externes : c'est le
serveur SafeCity qui récupère les tuiles (fond CARTO « Voyager », style
OpenStreetMap coloré) et les met en cache sur disque, puis les sert depuis son
propre domaine — déjà autorisé par le pare-feu.

IMPORTANT : ce proxy ne fonctionne que si LE SERVEUR qui exécute le backend a un
accès Internet vers le CDN. Si le CDN est injoignable (réseau filtré), le proxy
échoue vite et sert un fond neutre 200 (au lieu de 502) afin que la carte reste
lisible (marqueurs/itinéraires) sans casser ni saturer le journal.

Route : GET /tiles/<z>/<x>/<y>.png
"""
import logging
import os
import struct
import threading
import time
import urllib.request
import zlib

from flask import Blueprint, Response, current_app, send_file

log = logging.getLogger("safecity")

bp = Blueprint("tiles", __name__)

# Fond CARTO Voyager (coloré, style OSM). Un seul hôte : le cache disque évite
# de solliciter le CDN à chaque requête.
_UPSTREAM = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
_UA = "SafeCity/1.0 (municipal safety platform)"
_TIMEOUT = 6  # s — échoue vite si le CDN est injoignable (au lieu de bloquer)

# --- Repli quand le CDN est injoignable ---------------------------------- #
# Après quelques échecs, on cesse de solliciter le réseau pendant COOLDOWN
# secondes et on sert directement une tuile neutre : la carte reste utilisable,
# le journal n'est pas inondé, et on retente automatiquement plus tard.
_FAIL_THRESHOLD = 3
_COOLDOWN = 60
_lock = threading.Lock()
_fail_count = 0
_cooldown_until = 0.0


def _make_solid_png(rgb=(233, 237, 242), size=256):
    """Génère une tuile PNG unie (couleur du fond de carte) sans dépendance."""
    row = bytes([0]) + bytes(rgb) * size  # octet de filtre + pixels RVB
    raw = row * size

    def _chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # RVB 8 bits
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


_FALLBACK_TILE = _make_solid_png()


def _fallback_response():
    resp = Response(_FALLBACK_TILE, mimetype="image/png")
    # Cache court : on réessaiera le vrai fond dès que le réseau reviendra.
    resp.headers["Cache-Control"] = "public, max-age=30"
    return resp


def _upstream_in_cooldown():
    return time.time() < _cooldown_until


def _note_failure(z, x, y, err):
    global _fail_count, _cooldown_until
    with _lock:
        _fail_count += 1
        entering = _fail_count == _FAIL_THRESHOLD and not _upstream_in_cooldown()
        if _fail_count >= _FAIL_THRESHOLD:
            _cooldown_until = time.time() + _COOLDOWN
    # Ne journalise qu'à l'entrée en repli (évite d'inonder le journal).
    if entering:
        log.warning("Fond de carte indisponible (le serveur ne joint pas le CDN "
                    "de tuiles : %s). Repli sur un fond neutre pendant %ss.",
                    err, _COOLDOWN)


def _note_success():
    global _fail_count, _cooldown_until
    if _fail_count or _cooldown_until:
        with _lock:
            _fail_count = 0
            _cooldown_until = 0.0


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
    if os.path.exists(path) and os.path.getsize(path) > 0:
        resp = send_file(path, mimetype="image/png", conditional=True)
        resp.headers["Cache-Control"] = "public, max-age=2592000"  # 30 jours
        return resp

    # Pas en cache : si le CDN vient d'échouer, on sert le fond neutre sans même
    # tenter le réseau (évite des dizaines de timeouts à chaque déplacement).
    if _upstream_in_cooldown():
        return _fallback_response()

    url = _UPSTREAM.format(z=z, x=x, y=y)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = resp.read()
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
        _note_success()
    except Exception as e:  # pragma: no cover - dépend du réseau du serveur
        _note_failure(z, x, y, e)
        return _fallback_response()

    resp = send_file(path, mimetype="image/png", conditional=True)
    resp.headers["Cache-Control"] = "public, max-age=2592000"  # 30 jours
    return resp
