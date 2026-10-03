"""Fonctions géographiques : distance, temps d'intervention estimé,
et résolution approximative du quartier / adresse à partir du GPS.
"""
import json
import logging
import math
import threading
import time
import urllib.parse
import urllib.request

log = logging.getLogger("safecity")

# Vitesses moyennes utilisées pour l'estimation du temps d'intervention.
MOTO_SPEED_KMH = 25.0   # moto en zone urbaine
WALK_SPEED_KMH = 5.0    # marche à pied


def haversine_m(lat1, lng1, lat2, lng2):
    """Distance en mètres entre deux points GPS (formule de Haversine)."""
    r = 6371000.0  # rayon terrestre (m)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def eta_minutes(distance_m, speed_kmh):
    """Temps de trajet estimé (minutes) pour une distance et une vitesse."""
    if distance_m is None or speed_kmh <= 0:
        return None
    hours = (distance_m / 1000.0) / speed_kmh
    return round(hours * 60.0, 1)


def compute_intervention(patrol_lat, patrol_lng, alert_lat, alert_lng):
    """Retourne (distance_m, eta_moto_min, eta_walk_min) entre une patrouille
    et une alerte. Renvoie des None si les coordonnées patrouille manquent."""
    if patrol_lat is None or patrol_lng is None:
        return None, None, None
    dist = haversine_m(patrol_lat, patrol_lng, alert_lat, alert_lng)
    return (
        dist,
        eta_minutes(dist, MOTO_SPEED_KMH),
        eta_minutes(dist, WALK_SPEED_KMH),
    )


def coords_label(lat, lng):
    """Libellé lisible des coordonnées exactes (localisateur toujours fiable)."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lng >= 0 else "O"
    return f"{abs(lat):.5f}°{ns}, {abs(lng):.5f}°{ew}"


_GEO_CACHE = {}
_GEO_LOCK = threading.Lock()
# Politique d'usage de Nominatim : au plus 1 requête par seconde pour tout le
# serveur (sinon l'adresse IP de la mairie peut être bloquée).
_RATE_LOCK = threading.Lock()
_last_call = [0.0]
_MIN_INTERVAL = 1.05


def _throttle():
    with _RATE_LOCK:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


# Centre de Lubumbashi et ses communes officielles : sert à classer les champs
# OpenStreetMap (qui varient d'un endroit à l'autre) et à renseigner la ville.
LUBUMBASHI_CENTER = (-11.6647, 27.4794)
LUBUMBASHI_RADIUS_M = 30000
LUBUMBASHI_COMMUNES = ("Lubumbashi", "Kamalondo", "Kenya", "Katuba",
                       "Kampemba", "Rwashi", "Annexe")


def _norm(s):
    s = (s or "").strip()
    for prefix in ("Commune de ", "Commune d'", "Commune ", "commune de ", "commune "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip()


def _known_commune(value):
    v = _norm(value).lower()
    for c in LUBUMBASHI_COMMUNES:
        if v == c.lower():
            return c
    return None


# Certains champs Nominatim (« suburb », « residential »…) contiennent parfois
# le nom d'une avenue/rue au lieu d'un vrai quartier — une particularité des
# données OpenStreetMap, plus fréquente là où le découpage administratif est
# peu détaillé (cas de plusieurs zones de Lubumbashi). On écarte ces valeurs
# plutôt que de les afficher dans le mauvais champ (jamais de quartier inventé
# : si tout est écarté, le quartier reste simplement vide).
_STREET_PREFIXES = ("avenue ", "av. ", "av ", "rue ", "boulevard ", "bd ",
                    "route ", "chaussée ", "chaussee ", "place ")


def _looks_like_street(value):
    v = (value or "").strip().lower()
    return any(v.startswith(p) for p in _STREET_PREFIXES)


def default_city(lat, lng):
    """« Lubumbashi » si le point est dans l'agglomération, sinon None."""
    try:
        d = haversine_m(lat, lng, *LUBUMBASHI_CENTER)
    except Exception:
        return None
    return "Lubumbashi" if d <= LUBUMBASHI_RADIUS_M else None


def parse_osm_address(addr, lat=None, lng=None):
    """Transforme l'« address » Nominatim en champs SafeCity.

    Renvoie un dict : street (avenue/rue), neighborhood (quartier), commune,
    city (ville). Les champs inconnus valent None — jamais inventés.

    Nominatim ne range pas toujours la même information dans le même champ
    (surtout en RDC, où le découpage administratif est inégalement détaillé
    dans OpenStreetMap) : on inspecte donc plusieurs champs candidats pour
    chaque niveau, et on écarte toute valeur qui ressemble à une avenue/rue
    plutôt que de la mettre dans le mauvais champ.
    """
    addr = addr or {}
    street = (addr.get("road") or addr.get("pedestrian") or addr.get("footway")
              or addr.get("residential") or None)
    if street and addr.get("house_number"):
        street = f"{street} n° {addr['house_number']}"

    # Commune : d'abord une commune officielle de Lubumbashi trouvée dans
    # n'importe quel champ, sinon les champs administratifs usuels — jamais
    # une valeur qui ressemble à une avenue/rue.
    commune = None
    for key in ("city_district", "municipality", "borough", "suburb", "district",
                "county", "quarter", "neighbourhood"):
        v = addr.get(key)
        if v and _looks_like_street(v):
            continue
        commune = _known_commune(v)
        if commune:
            break
    if not commune:
        for key in ("city_district", "municipality", "borough"):
            v = _norm(addr.get(key))
            if v and not _looks_like_street(v):
                commune = v
                break

    # Quartier : le niveau le plus fin, différent de la commune, jamais une
    # avenue/rue (certains champs — « suburb », « residential »… — contiennent
    # parfois un nom de rue selon les données disponibles à cet endroit : on
    # passe alors au champ candidat suivant plutôt que de l'afficher à tort).
    neighborhood = None
    for key in ("neighbourhood", "quarter", "suburb", "residential", "hamlet",
                "city_block", "village"):
        v = _norm(addr.get(key))
        if not v or _looks_like_street(v):
            continue
        if commune and v.lower() == commune.lower():
            continue
        neighborhood = v
        break

    # Ville : dans l'agglomération de Lubumbashi, la position GPS est plus
    # fiable que le champ « city » de Nominatim (qui retombe parfois sur une
    # province voisine, ex. « Lualaba », faute de limite communale précise
    # dans OpenStreetMap à cet endroit). Ailleurs, on fait confiance au
    # service — déterminé dynamiquement, jamais « Lubumbashi » imposé partout.
    geo_city = default_city(lat, lng) if lat is not None and lng is not None else None
    city = geo_city or addr.get("city") or addr.get("town") or None

    return {"street": street, "neighborhood": neighborhood,
            "commune": commune, "city": city}


def reverse_geocode_details(lat, lng, timeout=6):
    """Adresse détaillée réelle via Nominatim (OpenStreetMap).

    Renvoie un dict (street, neighborhood, commune, city, address) ou None si
    le service est injoignable — on n'invente jamais de faux lieu.
    """
    key = (round(lat, 4), round(lng, 4))   # ≈ 11 m : inutile de réinterroger
    with _GEO_LOCK:
        if key in _GEO_CACHE:
            return _GEO_CACHE[key]
    try:
        params = urllib.parse.urlencode({
            "format": "jsonv2", "lat": lat, "lon": lng, "zoom": 18,
            "addressdetails": 1, "accept-language": "fr",
        })
        url = "https://nominatim.openstreetmap.org/reverse?" + params
        req = urllib.request.Request(url, headers={
            "User-Agent": "SafeCity/1.0 (plateforme municipale de securite - Lubumbashi)",
        })
        _throttle()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        # Journal de debug temporaire (niveau DEBUG seulement, donc invisible
        # en production par défaut) : la réponse brute de Nominatim, pour
        # vérifier quels champs sont réellement renvoyés à un endroit donné.
        log.debug("Géocodage inverse (%.5f, %.5f) — réponse Nominatim address=%s",
                 lat, lng, data.get("address"))
        d = parse_osm_address(data.get("address", {}), lat, lng)
        parts = [d["street"], d["neighborhood"], d["commune"], d["city"]]
        d["address"] = ", ".join(p for p in parts if p) or data.get("display_name") \
            or coords_label(lat, lng)
        result = d
    except Exception as e:  # pragma: no cover - dépend du réseau du serveur
        # Jamais invoqué pour masquer l'échec : ce journal est ce qui permet de
        # diagnostiquer (réseau sortant bloqué, service désactivé, timeout…)
        # quand le géocodage reste indisponible sans raison visible côté client.
        log.warning("Géocodage inverse indisponible pour (%.5f, %.5f) : %s: %s",
                   lat, lng, type(e).__name__, e)
        return None     # pas mis en cache : on retentera à la prochaine alerte
    with _GEO_LOCK:
        if len(_GEO_CACHE) > 5000:      # borne mémoire
            _GEO_CACHE.clear()
        _GEO_CACHE[key] = result
    return result


def reverse_geocode(lat, lng, timeout=6):
    """Compatibilité : renvoie ``(quartier, adresse)`` (voir reverse_geocode_details)."""
    d = reverse_geocode_details(lat, lng, timeout)
    if not d:
        return (None, coords_label(lat, lng))
    return (d.get("neighborhood") or d.get("commune"), d.get("address"))


# --------------------------------------------------------------------------- #
# Itinéraire routier (agent -> alerte)
# --------------------------------------------------------------------------- #
_ROUTE_CACHE = {}
_ROUTE_TTL = 300          # s : un trajet change peu en 5 min
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"


def _direct_route(a_lat, a_lng, b_lat, b_lng):
    """Repli sans service de routage : ligne droite, distance routière estimée
    (+30 % de détours) et durée à la vitesse moyenne d'une moto en ville."""
    d = haversine_m(a_lat, a_lng, b_lat, b_lng) * 1.3
    return {"source": "direct", "coordinates": [[a_lat, a_lng], [b_lat, b_lng]],
            "distance_m": round(d), "duration_s": round((d / 1000.0) / MOTO_SPEED_KMH * 3600)}


def route(a_lat, a_lng, b_lat, b_lng, timeout=6):
    """Itinéraire le plus rapide entre deux points (OSRM / OpenStreetMap).

    Renvoie {source: "osrm"|"direct", coordinates: [[lat, lng], …],
    distance_m, duration_s}. Le poste opérateur n'appelle jamais OSRM
    directement (pare-feu) : c'est le serveur qui le fait, avec cache.
    """
    key = (round(a_lat, 3), round(a_lng, 3), round(b_lat, 4), round(b_lng, 4))  # ~100 m / 10 m
    now = time.monotonic()
    with _GEO_LOCK:
        hit = _ROUTE_CACHE.get(key)
        if hit and now - hit[0] < _ROUTE_TTL:
            return hit[1]
    try:
        url = (f"{OSRM_URL}{a_lng:.6f},{a_lat:.6f};{b_lng:.6f},{b_lat:.6f}"
               "?overview=full&geometries=geojson")
        req = urllib.request.Request(url, headers={
            "User-Agent": "SafeCity/1.0 (plateforme municipale de securite - Lubumbashi)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        r = (data.get("routes") or [None])[0]
        if not r:
            raise ValueError("aucun itinéraire")
        result = {"source": "osrm",
                  "coordinates": [[c[1], c[0]] for c in r["geometry"]["coordinates"]],
                  "distance_m": round(r.get("distance") or 0),
                  "duration_s": round(r.get("duration") or 0)}
    except Exception as e:  # pragma: no cover - dépend du réseau du serveur
        log.warning("Itinéraire OSRM indisponible (%s -> %s) : %s: %s",
                   (a_lat, a_lng), (b_lat, b_lng), type(e).__name__, e)
        return _direct_route(a_lat, a_lng, b_lat, b_lng)   # non mis en cache
    with _GEO_LOCK:
        if len(_ROUTE_CACHE) > 2000:
            _ROUTE_CACHE.clear()
        _ROUTE_CACHE[key] = (now, result)
    return result
