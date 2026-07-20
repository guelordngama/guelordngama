"""Authentification : inscription citoyenne et connexion (citoyens + personnels)."""
from flask import Blueprint, current_app, jsonify, request

from ..errors import AuthError
from ..models import User
from ..security import generate_token, rate_limit, verify_password
from ..services.auth import register_citizen
from ..validation import _is_email, validate_login_payload, validate_register_payload

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    # Même limitation que la connexion pour éviter la création massive de comptes.
    limiter = rate_limit(
        current_app.config["LOGIN_RATE_MAX"],
        current_app.config["LOGIN_RATE_WINDOW"],
        scope="register",
    )
    return limiter(_do_register)()


def _do_register():
    payload = validate_register_payload(request.get_json(silent=True))
    user = register_citizen(payload)
    return jsonify({"token": generate_token(user), "user": user.to_dict()}), 201


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
    identifier, password = validate_login_payload(request.get_json(silent=True))
    # L'identifiant est un e-mail (personnel) ou un numéro de téléphone (citoyen).
    if _is_email(identifier):
        user = User.query.filter_by(email=identifier).first()
    else:
        # Retrouve le compte quel que soit le format saisi (avec/sans « + »).
        digits = identifier.lstrip("+")
        candidates = {identifier, digits, "+" + digits}
        user = User.query.filter(User.phone.in_(candidates)).first()
    # Message générique : ne révèle pas si le compte existe.
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("Identifiants invalides.")
    if not user.active:
        raise AuthError("Ce compte est désactivé.")
    return jsonify({"token": generate_token(user), "user": user.to_dict()})
