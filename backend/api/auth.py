"""Authentification : inscription citoyenne et connexion (citoyens + personnels)."""
from flask import Blueprint, current_app, g, jsonify, request

from ..errors import AuthError
from ..models import User
from ..security import generate_token, rate_limit, require_auth, verify_password
from ..services import audit
from ..services.auth import (
    change_password,
    register_citizen,
    register_staff,
    request_password_reset,
    resend_otp,
    verify_otp,
)
from ..validation import (
    _is_email,
    validate_change_password_payload,
    validate_email_only,
    validate_login_payload,
    validate_phone_only,
    validate_register_payload,
    validate_staff_register_payload,
    validate_verify_otp_payload,
)

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
    audit.record("citizen_registered", detail=user.phone, user_id=user.id, user_name=user.name)
    # Pas de jeton tant que le téléphone n'est pas vérifié par code SMS.
    return jsonify({
        "verification_required": True,
        "phone": user.phone,
        "message": "Un code de vérification a été envoyé par SMS à votre numéro.",
    }), 201


@bp.post("/verify-otp")
def verify_otp_route():
    """Vérifie le code SMS et active le compte citoyen (renvoie un jeton)."""
    limiter = rate_limit(
        current_app.config["LOGIN_RATE_MAX"],
        current_app.config["LOGIN_RATE_WINDOW"],
        scope="otp",
    )
    return limiter(_do_verify_otp)()


def _do_verify_otp():
    phone, code = validate_verify_otp_payload(request.get_json(silent=True))
    user = verify_otp(phone, code)
    audit.record("phone_verified", detail=user.phone, user_id=user.id, user_name=user.name)
    return jsonify({"token": generate_token(user), "user": user.to_dict()})


@bp.post("/resend-otp")
def resend_otp_route():
    """Renvoie un code de vérification à un compte non encore vérifié."""
    limiter = rate_limit(
        current_app.config["LOGIN_RATE_MAX"],
        current_app.config["LOGIN_RATE_WINDOW"],
        scope="otp",
    )
    return limiter(_do_resend_otp)()


def _do_resend_otp():
    phone = validate_phone_only(request.get_json(silent=True))
    resend_otp(phone)
    return jsonify({
        "message": "Si un compte non vérifié existe pour ce numéro, un nouveau "
                   "code vient d'être envoyé par SMS.",
    })


@bp.post("/register-staff")
def register_staff_route():
    """Inscription d'un personnel (rôle opérateur) depuis la console bureau."""
    limiter = rate_limit(
        current_app.config["LOGIN_RATE_MAX"],
        current_app.config["LOGIN_RATE_WINDOW"],
        scope="register",
    )
    return limiter(_do_register_staff)()


def _do_register_staff():
    payload = validate_staff_register_payload(request.get_json(silent=True))
    user = register_staff(payload)
    audit.record("staff_created", detail=user.email, user_id=user.id, user_name=user.name)
    return jsonify({"token": generate_token(user), "user": user.to_dict()}), 201


@bp.post("/forgot-password")
def forgot_password():
    """Réinitialisation du mot de passe : envoie un mot de passe temporaire par e-mail."""
    limiter = rate_limit(
        current_app.config["LOGIN_RATE_MAX"],
        current_app.config["LOGIN_RATE_WINDOW"],
        scope="forgot",
    )
    return limiter(_do_forgot_password)()


def _do_forgot_password():
    email = validate_email_only(request.get_json(silent=True))
    request_password_reset(email)
    audit.record("password_reset_requested", detail=email, user_name=email)
    return jsonify({
        "message": "Si un compte existe pour cet e-mail, un mot de passe de "
                   "réinitialisation vient d'être envoyé. Vérifiez votre boîte Gmail."
    })


@bp.post("/change-password")
@require_auth()
def change_password_route():
    """Change le mot de passe de l'utilisateur connecté (bureau / portail)."""
    current, new = validate_change_password_payload(request.get_json(silent=True))
    change_password(int(g.user["sub"]), current, new)
    audit.record("password_changed")
    return jsonify({"message": "Mot de passe modifié avec succès."})


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
        audit.record("login_failed", detail=identifier, user_name=identifier)
        raise AuthError("Identifiants invalides.")
    if not user.active:
        audit.record("login_denied_inactive", detail=identifier,
                     user_id=user.id, user_name=user.name)
        raise AuthError("Ce compte est désactivé.")
    if user.role == "citizen" and not user.phone_verified:
        audit.record("login_unverified", detail=identifier,
                     user_id=user.id, user_name=user.name)
        raise AuthError("Votre numéro n'est pas encore vérifié.",
                        code="phone_not_verified")
    audit.record("login", detail=f"{user.email or user.phone} ({user.role})",
                 user_id=user.id, user_name=user.name)
    return jsonify({"token": generate_token(user), "user": user.to_dict()})
