"""Gestion centralisée des erreurs de l'API SafeCity.

Toutes les erreurs applicatives héritent d'`ApiError` et sont sérialisées en
JSON de façon homogène : {"error": {"message": ..., "code": ...}}.
"""
import logging

from werkzeug.exceptions import HTTPException

log = logging.getLogger("safecity")


class ApiError(Exception):
    """Erreur applicative avec code HTTP et message destiné au client."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message, status_code=None, code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details

    def to_dict(self):
        payload = {"error": {"message": self.message, "code": self.code}}
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class ValidationError(ApiError):
    status_code = 400
    code = "validation_error"


class AuthError(ApiError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(ApiError):
    status_code = 403
    code = "forbidden"


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    """Conflit avec une ressource existante (ex. numéro de téléphone déjà pris)."""

    status_code = 409
    code = "conflict"


class RateLimitError(ApiError):
    status_code = 429
    code = "rate_limited"


def register_error_handlers(app):
    from flask import jsonify

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return (
            jsonify({"error": {"message": err.description, "code": err.name.lower().replace(" ", "_")}}),
            err.code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        # Journalise la trace complète côté serveur, ne l'expose jamais au client.
        log.exception("Erreur interne non gérée : %s", err)
        return (
            jsonify({"error": {"message": "Erreur interne du serveur", "code": "internal_error"}}),
            500,
        )
