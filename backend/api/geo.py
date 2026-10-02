"""Adresse d'une position GPS pour l'application citoyenne.

GET /api/geo/reverse?lat=-11.68&lng=27.50
  -> {"available": true, "street": "Avenue Sendwe", "neighborhood": "Bongonga",
      "commune": "Kenya", "city": "Lubumbashi"}

Le téléphone du citoyen ne peut pas joindre OpenStreetMap directement (pare-feu
de la mairie) : c'est le serveur qui interroge le service, avec cache et
limitation de débit. Aucun lieu n'est inventé : champ inconnu = null.
"""
import logging

from flask import Blueprint, current_app, jsonify, request

from ..geo import default_city, reverse_geocode_details, route as compute_route
from ..security import rate_limit, require_auth
from ..validation import validate_coordinates

log = logging.getLogger("safecity")

bp = Blueprint("geo", __name__, url_prefix="/api/geo")


@bp.get("/reverse")
@rate_limit(30, 60, scope="geo_reverse")
def reverse():
    lat, lng = validate_coordinates(request.args.get("lat"), request.args.get("lng"))
    empty = {"street": None, "neighborhood": None, "commune": None,
             "city": default_city(lat, lng)}
    if not current_app.config.get("GEOCODING_ENABLED", True):
        log.warning("Géocodage inverse désactivé (SAFECITY_GEOCODING) : "
                   "requête (%.5f, %.5f) renvoyée sans adresse.", lat, lng)
        return jsonify(dict(empty, available=False))
    details = reverse_geocode_details(lat, lng)
    if not details:
        return jsonify(dict(empty, available=False))
    return jsonify({
        "available": True,
        "street": details.get("street"),
        "neighborhood": details.get("neighborhood"),
        "commune": details.get("commune"),
        "city": details.get("city") or empty["city"],
    })


@bp.get("/route")
@require_auth(roles=["operator", "supervisor", "admin", "agent"])
@rate_limit(120, 60, scope="geo_route")
def route():
    """Itinéraire agent -> alerte : ?from=lat,lng&to=lat,lng (réservé au personnel)."""
    from ..errors import ValidationError

    def pt(name):
        raw = (request.args.get(name) or "").split(",")
        if len(raw) != 2:
            raise ValidationError(f"Paramètre « {name} » attendu : lat,lng")
        return validate_coordinates(raw[0], raw[1])

    a, b = pt("from"), pt("to")
    if not current_app.config.get("GEOCODING_ENABLED", True):
        from ..geo import _direct_route
        return jsonify(_direct_route(a[0], a[1], b[0], b[1]))
    return jsonify(compute_route(a[0], a[1], b[0], b[1]))
