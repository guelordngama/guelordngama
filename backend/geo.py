"""Fonctions géographiques : distance, temps d'intervention estimé,
et résolution approximative du quartier / adresse à partir du GPS.
"""
import json
import math
import threading
import urllib.parse
import urllib.request

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
    """
    addr = addr or {}
    street = (addr.get("road") or addr.get("pedestrian") or addr.get("footway")
              or addr.get("residential") or None)
    if street and addr.get("house_number"):
        street = f"{street} n° {addr['house_number']}"

    # Commune : d'abord une commune officielle de Lubumbashi trouvée dans
    # n'importe quel champ, sinon les champs administratifs usuels.
    commune = None
    for key in ("city_district", "municipality", "borough", "suburb", "district",
                "county", "quarter", "neighbourhood"):
        commune = _known_commune(addr.get(key))
        if commune:
            break
    if not commune:
        commune = _norm(addr.get("city_district") or addr.get("municipality")
                        or addr.get("borough")) or None

    # Quartier : le niveau le plus fin, différent de la commune.
    neighborhood = None
    for key in ("neighbourhood", "quarter", "suburb", "residential", "hamlet",
                "city_block", "village"):
        v = _norm(addr.get(key))
        if v and (not commune or v.lower() != commune.lower()):
            neighborhood = v
            break

    city = addr.get("city") or addr.get("town") or None
    if not city and lat is not None and lng is not None:
        city = default_city(lat, lng)
    return {"street": street, "neighborhood": neighborhood,
            "commune": commune, "city": city}


def reverse_geocode_details(lat, lng, timeout=6):
    """Adresse détaillée réelle via Nominatim (OpenStreetMap).

    Renvoie un dict (street, neighborhood, commune, city, address) ou None si
    le service est injoignable — on n'invente jamais de faux lieu.
    """
    key = (round(lat, 5), round(lng, 5))
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        d = parse_osm_address(data.get("address", {}), lat, lng)
        parts = [d["street"], d["neighborhood"], d["commune"], d["city"]]
        d["address"] = ", ".join(p for p in parts if p) or data.get("display_name") \
            or coords_label(lat, lng)
        result = d
    except Exception:  # pragma: no cover - dépend du réseau du serveur
        return None     # pas mis en cache : on retentera à la prochaine alerte
    with _GEO_LOCK:
        _GEO_CACHE[key] = result
    return result


def reverse_geocode(lat, lng, timeout=6):
    """Compatibilité : renvoie ``(quartier, adresse)`` (voir reverse_geocode_details)."""
    d = reverse_geocode_details(lat, lng, timeout)
    if not d:
        return (None, coords_label(lat, lng))
    return (d.get("neighborhood") or d.get("commune"), d.get("address"))
