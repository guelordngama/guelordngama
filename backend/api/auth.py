"""Authentification des opérateurs."""
from flask import Blueprint, current_app, jsonify, request

from ..errors import AuthError
from ..extensions import db
from ..models import User
from ..security import generate_token, rate_limit, verify_password
from ..validation import validate_login_payload

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    # Limitation stricte pour contrer les attaques par force brute.
    limiter = rate_limit(
        current_app.config["LOGIN_RATE_MAX"],
        current_app.config["LOGIN_RATE_WINDOW"],
        scope="login",
    )
    return limiter(_do_login)()


def _do_login():
    email, password = validate_login_payload(request.get_json(silent=True))
    user = User.query.filter_by(email=email).first()
    # Message générique : ne révèle pas si l'email existe.
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("Identifiants invalides.")
    return jsonify({"token": generate_token(user), "user": user.to_dict()})
