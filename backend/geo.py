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


def reverse_geocode(lat, lng, timeout=6):
    """Résout le quartier et l'adresse réels via Nominatim (OpenStreetMap).

    Renvoie ``(quartier, adresse)``. En cas d'indisponibilité (réseau, hors
    ligne), on renvoie ``(None, coordonnées)`` — jamais un faux quartier : la
    position GPS exacte reste le localisateur fiable pour la patrouille.
    """
    fallback = (None, coords_label(lat, lng))
    key = (round(lat, 4), round(lng, 4))
    with _GEO_LOCK:
        if key in _GEO_CACHE:
            return _GEO_CACHE[key]
    try:
        params = urllib.parse.urlencode({
            "format": "jsonv2", "lat": lat, "lon": lng, "zoom": 16,
            "addressdetails": 1, "accept-language": "fr",
        })
        url = "https://nominatim.openstreetmap.org/reverse?" + params
        req = urllib.request.Request(url, headers={
            "User-Agent": "SafeCity/1.0 (plateforme municipale de securite - Lubumbashi)",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        addr = data.get("address", {}) or {}
        neigh = (addr.get("suburb") or addr.get("neighbourhood") or addr.get("quarter")
                 or addr.get("city_district") or addr.get("residential")
                 or addr.get("village") or addr.get("town") or addr.get("municipality"))
        parts = [addr.get("road"), neigh, addr.get("city") or addr.get("town")]
        address = ", ".join([p for p in parts if p]) or data.get("display_name") \
            or coords_label(lat, lng)
        result = (neigh, address)
    except Exception:  # pragma: no cover - dépend du réseau du serveur
        result = fallback
    with _GEO_LOCK:
        _GEO_CACHE[key] = result
    return result
