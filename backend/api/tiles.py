"""Proxy de tuiles de carte.

Permet aux clients (poste opérateur, portail, site citoyen) d'afficher la carte
même lorsque le réseau local bloque les CDN de tuiles externes : c'est le
serveur SafeCity qui récupère les tuiles (fond OpenStreetMap, avec un
fournisseur de secours) et les met en cache sur disque, puis les sert depuis son
propre domaine — déjà autorisé par le pare-feu.

Historique : CARTO exige désormais une clé API et renvoie des tuiles barrées
« API KEY REQUIRED » ; il n'est plus utilisé. La route versionnée
/tiles/v2/… garantit qu'aucune ancienne tuile (cache navigateur) ne réapparaît.

IMPORTANT : ce proxy ne fonctionne que si LE SERVEUR qui exécute le backend a un
accès Internet vers le CDN. Si le CDN est injoignable (réseau filtré), le proxy
échoue vite et sert un fond neutre 200 (au lieu de 502) afin que la carte reste
lisible (marqueurs/itinéraires) sans casser ni saturer le journal.

Routes : GET /tiles/v2/<z>/<x>/<y>.png (et l'ancienne /tiles/<z>/<x>/<y>.png)
Fournisseurs configurables : SAFECITY_TILE_URLS (liste séparée par des virgules,
gabarits {z}/{x}/{y}), essayés dans l'ordre.
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

# Fournisseurs sans clé, essayés dans l'ordre : OpenStreetMap (fond standard),
# puis Esri World Street Map en secours. Le cache disque évite de solliciter
# les serveurs à chaque requête (politique d'usage OSM).
DEFAULT_UPSTREAMS = (
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
)
_UA = "SafeCity-Lubumbashi/1.23 (+https://safecity-lubumbashi.com; plateforme municipale)"
_CACHE_VERSION = "v2"     # nouveau fond : ignore les tuiles CARTO « API KEY REQUIRED »
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


_purged = False


def _cache_dir():
    global _purged
    root = current_app.config.get("TILECACHE_DIR")
    if not root:
        root = os.path.join(current_app.config["UPLOAD_DIR"], "..", "tilecache")
    root = os.path.abspath(root)
    d = os.path.join(root, _CACHE_VERSION)
    os.makedirs(d, exist_ok=True)
    if not _purged:
        # Supprime une fois les anciennes tuiles CARTO (barrées « API KEY REQUIRED »).
        _purged = True
        try:
            for name in os.listdir(root):
                if name.endswith(".png"):
                    os.remove(os.path.join(root, name))
        except OSError:
            pass
    return d


def _upstreams():
    raw = current_app.config.get("TILE_URLS") or ""
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    return urls or list(DEFAULT_UPSTREAMS)


def _fetch(z, x, y):
    """Récupère la tuile chez le premier fournisseur qui répond (image valide)."""
    last = None
    for tpl in _upstreams():
        try:
            req = urllib.request.Request(tpl.format(z=z, x=x, y=y), headers={
                "User-Agent": _UA, "Referer": "https://safecity-lubumbashi.com/"})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                ctype = resp.headers.get("Content-Type", "")
                data = resp.read()
            if not ctype.startswith("image/") or len(data) < 100:
                raise ValueError(f"réponse non image ({ctype}, {len(data)} o)")
            return data
        except Exception as e:  # on essaie le fournisseur suivant
            last = e
    raise last or RuntimeError("aucun fournisseur de tuiles")


@bp.get("/tiles/<int:z>/<int:x>/<int:y>.png")
@bp.get("/tiles/v2/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    # Bornes de sécurité (évite les requêtes absurdes).
    if not (0 <= z <= 20) or not (0 <= x < (1 << z)) or not (0 <= y < (1 << z)):
        return Response("bad tile", status=400)

    path = os.path.join(_cache_dir(), f"{z}_{x}_{y}.png")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        resp = send_file(path, mimetype="image/png", conditional=True)
        resp.headers["Cache-Control"] = "public, max-age=604800"  # 7 jours
        return resp

    # Pas en cache : si le CDN vient d'échouer, on sert le fond neutre sans même
    # tenter le réseau (évite des dizaines de timeouts à chaque déplacement).
    if _upstream_in_cooldown():
        return _fallback_response()

    try:
        data = _fetch(z, x, y)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
        _note_success()
    except Exception as e:  # pragma: no cover - dépend du réseau du serveur
        _note_failure(z, x, y, e)
        return _fallback_response()

    resp = send_file(path, mimetype="image/png", conditional=True)
    resp.headers["Cache-Control"] = "public, max-age=604800"  # 7 jours
    return resp
