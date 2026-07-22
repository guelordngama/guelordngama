"""Service d'authentification : inscription des citoyens.

La connexion (login) reste gérée dans `api/auth.py` ; ce module porte la logique
métier de création de compte citoyen, dont la vérification d'unicité du numéro
de téléphone.
"""
import logging
import secrets

from ..errors import AuthError, ConflictError, ForbiddenError, ServiceUnavailableError
from ..extensions import db
from ..models import User
from ..security import hash_password, verify_password

log = logging.getLogger("safecity")


def _phone_candidates(phone):
    """Variantes d'un numéro pour la comparaison (avec/sans « + »)."""
    digits = phone.lstrip("+")
    return {phone, digits, "+" + digits}


def register_citizen(payload):
    """Crée un compte citoyen à partir d'une charge utile déjà validée.

    `payload` : {name, phone, password, email?}.

    Lève ConflictError si le numéro de téléphone (ou l'e-mail) est déjà utilisé.
    Retourne l'utilisateur créé.
    """
    phone = payload["phone"]

    # Le numéro de téléphone identifie le citoyen : il doit être unique.
    # On compare sur les chiffres pour que « +243810000111 », « 243810000111 »
    # ou « +243 810 000 111 » soient reconnus comme le même numéro.
    if User.query.filter(User.phone.in_(_phone_candidates(phone))).first():
        raise ConflictError(
            "Ce numéro de téléphone est déjà utilisé. Connectez-vous avec vos "
            "identifiants ou utilisez un autre numéro.",
            details={"field": "phone"},
        )

    email = payload.get("email")
    if email and User.query.filter_by(email=email).first():
        raise ConflictError(
            "Cet e-mail est déjà associé à un compte. Connectez-vous ou "
            "utilisez un autre e-mail.",
            details={"field": "email"},
        )

    user = User(
        name=payload["name"],
        phone=phone,
        email=email,
        role="citizen",
        password_hash=hash_password(payload["password"]),
    )
    db.session.add(user)
    db.session.commit()
    log.info("Nouveau compte citoyen #%s (%s)", user.id, phone)
    return user


def register_staff(payload):
    """Crée un compte personnel (rôle **opérateur**) depuis la console bureau.

    `payload` : {name, email, password, phone?, invite_code}. Un **code
    d'invitation** valide est exigé (sécurité). Si aucun code n'est configuré
    côté serveur, l'auto-inscription est désactivée. L'e-mail sert d'identifiant
    de connexion et doit être unique.
    """
    from flask import current_app

    required_code = current_app.config.get("STAFF_INVITE_CODE", "")
    if not required_code:
        raise ForbiddenError(
            "La création de compte est désactivée. Contactez l'administrateur "
            "pour obtenir un accès.")
    if (payload.get("invite_code") or "") != required_code:
        raise ForbiddenError("Code d'invitation invalide.")

    email = payload["email"]
    if User.query.filter_by(email=email).first():
        raise ConflictError(
            "Cet e-mail est déjà associé à un compte. Connectez-vous ou "
            "utilisez un autre e-mail.",
            details={"field": "email"},
        )

    phone = payload.get("phone")
    if phone and User.query.filter(User.phone.in_(_phone_candidates(phone))).first():
        raise ConflictError(
            "Ce numéro de téléphone est déjà utilisé.",
            details={"field": "phone"},
        )

    user = User(
        name=payload["name"],
        email=email,
        phone=phone,
        role="operator",
        password_hash=hash_password(payload["password"]),
    )
    db.session.add(user)
    db.session.commit()
    log.info("Nouveau compte opérateur #%s (%s)", user.id, email)
    return user


def _generate_temp_password(length=12):
    """Mot de passe temporaire lisible (sans caractères ambigus 0/O, 1/l)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def request_password_reset(email):
    """Réinitialise le mot de passe d'un compte et envoie le nouveau par e-mail.

    - Si aucun SMTP n'est configuré → lève ServiceUnavailableError
      (`email_not_configured`) : la réinitialisation par e-mail est impossible.
    - Sinon, si un compte **actif** existe pour cet e-mail, un mot de passe
      temporaire est généré, envoyé par e-mail, puis enregistré **seulement si
      l'envoi réussit** (pas de verrouillage du compte en cas d'échec SMTP).
    - La réponse de l'API reste générique (anti-énumération) : on ne révèle pas
      si le compte existe, sauf en cas d'échec d'envoi (compte existant).
    """
    from . import notifications

    if not notifications.smtp_configured():
        raise ServiceUnavailableError(
            "L'envoi d'e-mail n'est pas configuré sur le serveur. Configurez "
            "SAFECITY_SMTP_* (Gmail) pour activer la réinitialisation par e-mail.",
            code="email_not_configured",
        )

    user = User.query.filter_by(email=email).first()
    if not user or not user.active:
        return  # réponse générique : ne rien révéler

    temp = _generate_temp_password()
    subject = "SafeCity — Réinitialisation de votre mot de passe"
    body = (
        f"Bonjour {user.name},\n\n"
        "Vous avez demandé la réinitialisation de votre mot de passe SafeCity.\n\n"
        f"Nouveau mot de passe temporaire : {temp}\n\n"
        "Connectez-vous avec ce mot de passe, puis changez-le dès que possible "
        "depuis les paramètres.\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, prévenez immédiatement "
        "l'administrateur.\n\n— SafeCity"
    )

    # Envoyer d'abord ; ne modifier le mot de passe QUE si l'e-mail part bien.
    try:
        notifications.send_email_message([email], subject, body)
    except Exception as e:  # pragma: no cover - dépend du réseau/SMTP
        log.warning("Échec envoi e-mail de réinitialisation (%s) : %s", email, e)
        raise ServiceUnavailableError(
            "Impossible d'envoyer l'e-mail de réinitialisation. Vérifiez la "
            "configuration SMTP (Gmail) du serveur.",
            code="email_send_failed",
            status_code=502,
        )

    user.password_hash = hash_password(temp)
    db.session.commit()
    log.info("Mot de passe réinitialisé et envoyé par e-mail pour #%s", user.id)


def change_password(user_id, current_password, new_password):
    """Change le mot de passe d'un utilisateur connecté (après vérification)."""
    user = User.query.get(user_id)
    if not user:
        raise AuthError("Utilisateur introuvable.")
    if not verify_password(current_password, user.password_hash):
        raise AuthError("Mot de passe actuel incorrect.")
    user.password_hash = hash_password(new_password)
    db.session.commit()
    log.info("Mot de passe changé pour #%s", user.id)
    return user
