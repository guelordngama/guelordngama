"""Validation et nettoyage des entrées de l'API (sans dépendance externe).

Fournit de petits validateurs composables qui lèvent `ValidationError` avec un
message clair. Volontairement léger pour éviter d'ajouter une dépendance et
garder l'installation simple.
"""
from .errors import ValidationError
from .models import DANGER_TYPES


def require_dict(data):
    if not isinstance(data, dict):
        raise ValidationError("Corps de requête JSON attendu.")
    return data


def coerce_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Le champ '{field}' doit être un nombre.")


def validate_coordinates(lat, lng):
    lat = coerce_float(lat, "lat")
    lng = coerce_float(lng, "lng")
    if not (-90.0 <= lat <= 90.0):
        raise ValidationError("Latitude hors bornes (-90..90).")
    if not (-180.0 <= lng <= 180.0):
        raise ValidationError("Longitude hors bornes (-180..180).")
    return lat, lng


def clean_text(value, max_len=2000):
    if value is None:
        return ""
    text = str(value).strip()
    return text[:max_len]


def validate_alert_payload(data):
    """Valide et normalise la charge utile de création d'alerte.

    Retourne un dict propre : type, description, lat, lng, address, neighborhood,
    photo, audio, reporter_id.
    """
    data = require_dict(data)

    if "lat" not in data or "lng" not in data:
        raise ValidationError("Coordonnées GPS (lat, lng) requises.")
    lat, lng = validate_coordinates(data.get("lat"), data.get("lng"))

    declared_type = clean_text(data.get("type"), 30).lower() or "autre"
    if declared_type not in DANGER_TYPES:
        declared_type = "autre"

    return {
        "type": declared_type,
        "description": clean_text(data.get("description")),
        "lat": lat,
        "lng": lng,
        "address": clean_text(data.get("address"), 255) or None,
        "neighborhood": clean_text(data.get("neighborhood"), 120) or None,
        "reporter_name": clean_text(data.get("reporter_name"), 120) or None,
        "reporter_phone": clean_text(data.get("reporter_phone"), 40) or None,
        "photo": data.get("photo"),
        "audio": data.get("audio"),
        "reporter_id": data.get("reporter_id"),
    }


def validate_login_payload(data):
    data = require_dict(data)
    email = clean_text(data.get("email"), 160).lower()
    password = data.get("password") or ""
    if not email or not password:
        raise ValidationError("Email et mot de passe requis.")
    return email, password


def validate_team_id(data):
    data = require_dict(data)
    try:
        return int(data.get("team_id"))
    except (TypeError, ValueError):
        raise ValidationError("Le champ 'team_id' (entier) est requis.")
