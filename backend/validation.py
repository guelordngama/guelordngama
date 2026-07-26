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


def normalize_phone(value):
    """Normalise un numéro de téléphone pour la comparaison / le stockage.

    Conserve un éventuel « + » de tête et uniquement les chiffres (les espaces,
    tirets, points et parenthèses sont retirés). Retourne "" si vide.
    """
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    plus = raw.startswith("+")
    digits = "".join(ch for ch in raw if ch.isdigit())
    return ("+" + digits) if plus else digits


def _is_email(identifier):
    return "@" in identifier


def validate_login_payload(data):
    """Valide les identifiants de connexion.

    Accepte un identifiant sous forme d'e-mail (personnel) OU de numéro de
    téléphone (citoyen), via les champs `identifier`, `email` ou `phone`.
    Retourne (identifier_normalisé, password).
    """
    data = require_dict(data)
    raw = data.get("identifier") or data.get("email") or data.get("phone") or ""
    raw = str(raw).strip()
    password = data.get("password") or ""
    if not raw or not password:
        raise ValidationError("Identifiant et mot de passe requis.")
    identifier = raw.lower() if _is_email(raw) else normalize_phone(raw)
    return identifier, password


def validate_register_payload(data):
    """Valide l'inscription d'un citoyen.

    Champs : name (requis), phone (requis, unique vérifié côté service),
    password (requis, ≥ 6), email (optionnel).
    """
    data = require_dict(data)

    name = clean_text(data.get("name"), 120)
    if not name:
        raise ValidationError("Le nom est requis.")

    phone = normalize_phone(data.get("phone"))
    if not phone:
        raise ValidationError("Le numéro de téléphone est requis.")
    digits = phone.lstrip("+")
    if len(digits) < 8:
        raise ValidationError("Numéro de téléphone invalide (au moins 8 chiffres).")

    password = data.get("password") or ""
    if len(password) < 6:
        raise ValidationError("Le mot de passe doit contenir au moins 6 caractères.")

    if not bool(data.get("consent")):
        raise ValidationError(
            "Vous devez accepter la politique de confidentialité pour créer un compte.")

    email = clean_text(data.get("email"), 160).lower() or None
    if email and "@" not in email:
        raise ValidationError("Email invalide.")

    return {"name": name, "phone": phone, "password": password, "email": email}


def validate_staff_register_payload(data):
    """Valide l'inscription d'un personnel depuis la console bureau (rôle opérateur).

    Champs : name (requis), email (requis + valide), password (requis, ≥ 6),
    phone (optionnel).
    """
    data = require_dict(data)

    name = clean_text(data.get("name"), 120)
    if not name:
        raise ValidationError("Le nom est requis.")

    email = clean_text(data.get("email"), 160).lower()
    if not email or "@" not in email:
        raise ValidationError("Un e-mail valide est requis.")

    password = data.get("password") or ""
    if len(password) < 6:
        raise ValidationError("Le mot de passe doit contenir au moins 6 caractères.")

    phone = normalize_phone(data.get("phone")) or None
    invite_code = clean_text(data.get("invite_code"), 100)

    return {"name": name, "email": email, "password": password,
            "phone": phone, "invite_code": invite_code}


def validate_change_password_payload(data):
    """Valide un changement de mot de passe (utilisateur connecté)."""
    data = require_dict(data)
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""
    if not current:
        raise ValidationError("Le mot de passe actuel est requis.")
    if len(new) < 6:
        raise ValidationError("Le nouveau mot de passe doit contenir au moins 6 caractères.")
    if new == current:
        raise ValidationError("Le nouveau mot de passe doit être différent de l'actuel.")
    return current, new


def validate_email_only(data):
    """Valide une charge utile ne contenant qu'un e-mail (mot de passe oublié)."""
    data = require_dict(data)
    email = clean_text(data.get("email"), 160).lower()
    if not email or "@" not in email:
        raise ValidationError("Un e-mail valide est requis.")
    return email


def validate_verify_otp_payload(data):
    """Valide la vérification OTP : numéro + code."""
    data = require_dict(data)
    phone = normalize_phone(data.get("phone"))
    code = clean_text(data.get("code"), 12)
    if not phone or not code:
        raise ValidationError("Numéro de téléphone et code de vérification requis.")
    return phone, code


def validate_phone_only(data):
    """Valide une charge utile ne contenant qu'un numéro de téléphone (renvoi OTP)."""
    data = require_dict(data)
    phone = normalize_phone(data.get("phone"))
    if not phone:
        raise ValidationError("Numéro de téléphone requis.")
    return phone


def validate_reset_sms_payload(data):
    """Valide la réinitialisation par SMS : numéro + code + nouveau mot de passe."""
    data = require_dict(data)
    phone = normalize_phone(data.get("phone"))
    code = clean_text(data.get("code"), 12)
    new_password = data.get("new_password") or ""
    if not phone or not code:
        raise ValidationError("Numéro de téléphone et code requis.")
    if len(new_password) < 6:
        raise ValidationError("Le nouveau mot de passe doit contenir au moins 6 caractères.")
    return phone, code, new_password


def validate_team_id(data):
    data = require_dict(data)
    try:
        return int(data.get("team_id"))
    except (TypeError, ValueError):
        raise ValidationError("Le champ 'team_id' (entier) est requis.")


_STAFF_ROLES = {"agent", "operator", "supervisor", "admin"}


def validate_agent_payload(data, partial=False):
    """Valide la création/modification d'un personnel.

    partial=True (modification) : les champs absents sont ignorés.
    """
    data = require_dict(data)
    out = {}

    name = clean_text(data.get("name"), 120)
    if name:
        out["name"] = name
    elif not partial:
        raise ValidationError("Le nom est requis.")

    if "email" in data or not partial:
        email = clean_text(data.get("email"), 160).lower()
        if not email and not partial:
            raise ValidationError("L'email est requis.")
        if email and "@" not in email:
            raise ValidationError("Email invalide.")
        if email:
            out["email"] = email

    if "role" in data or not partial:
        role = clean_text(data.get("role"), 20).lower()
        if role and role not in _STAFF_ROLES:
            raise ValidationError("Rôle invalide (agent, operator, supervisor, admin).")
        if role:
            out["role"] = role
        elif not partial:
            raise ValidationError("Le rôle est requis.")

    if "phone" in data:
        out["phone"] = clean_text(data.get("phone"), 40) or None
    if "active" in data:
        out["active"] = bool(data.get("active"))

    password = data.get("password") or ""
    if password:
        if len(password) < 6:
            raise ValidationError("Le mot de passe doit contenir au moins 6 caractères.")
        out["password"] = password
    elif not partial:
        raise ValidationError("Le mot de passe est requis.")

    return out
