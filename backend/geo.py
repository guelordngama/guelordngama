"""Fonctions géographiques : distance, temps d'intervention estimé,
et résolution approximative du quartier / adresse à partir du GPS.
"""
import math

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


def reverse_geocode(lat, lng):
    """Résolution approximative quartier/adresse.

    En production, on appellerait un service (Nominatim/OpenStreetMap). Pour
    rester hors-ligne et sans dépendance réseau, on renvoie une désignation
    lisible fondée sur les coordonnées. Le champ reste modifiable côté client.
    """
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lng >= 0 else "O"
    address = f"{abs(lat):.5f}°{ns}, {abs(lng):.5f}°{ew}"
    # Quartier "pseudo" stable dérivé des coordonnées (placeholder déterministe).
    grid = int(abs(lat) * 1000) % 97 + int(abs(lng) * 1000) % 89
    neighborhood = f"Zone {grid:02d}"
    return neighborhood, address
