"""Adresse d'une position GPS pour l'application citoyenne.

GET /api/geo/reverse?lat=-11.68&lng=27.50
  -> {"available": true, "street": "Avenue Sendwe", "neighborhood": "Bongonga",
      "commune": "Kenya", "city": "Lubumbashi"}

Le téléphone du citoyen ne peut pas joindre OpenStreetMap directement (pare-feu
de la mairie) : c'est le serveur qui interroge le service, avec cache et
limitation de débit. Aucun lieu n'est inventé : champ inconnu = null.
"""
from flask import Blueprint, current_app, jsonify, request

from ..geo import default_city, reverse_geocode_details
from ..security import rate_limit
from ..validation import validate_coordinates

bp = Blueprint("geo", __name__, url_prefix="/api/geo")


@bp.get("/reverse")
@rate_limit(30, 60, scope="geo_reverse")
def reverse():
    lat, lng = validate_coordinates(request.args.get("lat"), request.args.get("lng"))
    empty = {"street": None, "neighborhood": None, "commune": None,
             "city": default_city(lat, lng)}
    if not current_app.config.get("GEOCODING_ENABLED", True):
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
