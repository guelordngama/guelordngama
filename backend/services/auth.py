"""Service d'authentification : inscription des citoyens.

La connexion (login) reste gérée dans `api/auth.py` ; ce module porte la logique
métier de création de compte citoyen, dont la vérification d'unicité du numéro
de téléphone.
"""
import logging
import secrets
from datetime import datetime, timedelta

from ..errors import (
    AuthError,
    ConflictError,
    ForbiddenError,
    ServiceUnavailableError,
    ValidationError,
)
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

    # Inscription directe : le compte est actif immédiatement (pas de code de
    # vérification). Le citoyen est connecté dès la création.
    user = User(
        name=payload["name"],
        phone=phone,
        email=email,
        role="citizen",
        password_hash=hash_password(payload["password"]),
        phone_verified=True,
        consent_at=datetime.utcnow(),  # consentement recueilli à l'inscription
    )
    db.session.add(user)
    db.session.commit()
    log.info("Nouveau compte citoyen #%s (%s) — activé", user.id, phone)
    return user


# --------------------------------------------------------------------------- #
# Vérification du téléphone (OTP par SMS)
# --------------------------------------------------------------------------- #
def _generate_otp(length):
    return "".join(secrets.choice("0123456789") for _ in range(length))


def send_otp(user):
    """Génère et envoie un code de vérification à l'utilisateur.

    Canaux, dans l'ordre :
      1. **SMS** vers le numéro (si une passerelle SMS est configurée) ;
      2. **repli e-mail** vers l'adresse du compte (si fournie et SMTP configuré)
         — l'inscription continue de fonctionner même si le SMS est indisponible.

    En production, échoue (503/502) si aucun canal n'aboutit ; en développement,
    journalise le code pour permettre les tests. Renvoie le canal utilisé
    (« sms », « email » ou « dev »).
    """
    from flask import current_app

    from . import notifications

    cfg = current_app.config
    code = _generate_otp(cfg["OTP_LENGTH"])
    user.otp_hash = hash_password(code)
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=cfg["OTP_TTL_MIN"])
    user.otp_attempts = 0
    db.session.commit()

    text = (f"SafeCity : votre code de vérification est {code}. "
            f"Valable {cfg['OTP_TTL_MIN']} minutes.")

    # 1) SMS (canal principal)
    if notifications.sms_configured():
        try:
            notifications.send_sms(user.phone, text)
            log.info("OTP envoyé par SMS au compte #%s", user.id)
            return "sms"
        except Exception as e:  # pragma: no cover - dépend du réseau/passerelle
            log.warning("Échec envoi OTP par SMS (#%s) : %s — tentative de repli e-mail", user.id, e)

    # 2) Repli e-mail (si le citoyen a fourni une adresse et le SMTP est configuré)
    if user.email and notifications.smtp_configured():
        try:
            notifications.send_email_message(
                [user.email], "SafeCity — code de vérification",
                f"Bonjour,\n\n{text}\n\n"
                "Saisissez ce code dans l'application pour activer votre compte.\n"
                "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.")
            log.info("OTP envoyé par e-mail (repli) au compte #%s", user.id)
            return "email"
        except Exception as e:  # pragma: no cover - dépend du réseau/SMTP
            log.warning("Échec envoi OTP par e-mail (#%s) : %s", user.id, e)

    # 3) Aucun canal n'a abouti
    if str(cfg.get("ENV", "development")).lower() == "production":
        raise ServiceUnavailableError(
            "Impossible d'envoyer le code de vérification (SMS et e-mail "
            "indisponibles). Réessayez plus tard ou contactez l'administrateur.",
            code="otp_send_failed", status_code=502)
    # Développement : code visible dans les logs serveur.
    log.warning("Aucun canal OTP configuré — CODE OTP (DEV) pour %s : %s", user.phone, code)
    return "dev"


def verify_otp(phone, code):
    """Vérifie le code OTP et active le compte (phone_verified=True).

    Retourne l'utilisateur vérifié, ou lève une erreur (code incorrect/expiré,
    trop de tentatives).
    """
    from flask import current_app

    from ..validation import normalize_phone

    phone_n = normalize_phone(phone)
    user = User.query.filter(User.phone.in_(_phone_candidates(phone_n))).first()
    if not user:
        raise AuthError("Compte introuvable pour ce numéro.")
    if user.phone_verified:
        return user  # déjà vérifié (idempotent)
    if not user.otp_hash or not user.otp_expires_at or datetime.utcnow() > user.otp_expires_at:
        raise ValidationError("Code expiré. Demandez un nouveau code.")
    if (user.otp_attempts or 0) >= current_app.config["OTP_MAX_ATTEMPTS"]:
        raise ValidationError("Trop de tentatives. Demandez un nouveau code.")
    if not verify_password(code, user.otp_hash):
        user.otp_attempts = (user.otp_attempts or 0) + 1
        db.session.commit()
        raise AuthError("Code de vérification incorrect.")

    user.phone_verified = True
    user.otp_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    db.session.commit()
    log.info("Téléphone vérifié pour le compte #%s", user.id)
    return user


def resend_otp(phone):
    """Renvoie un code de vérification à un compte non encore vérifié."""
    from ..validation import normalize_phone

    phone_n = normalize_phone(phone)
    user = User.query.filter(User.phone.in_(_phone_candidates(phone_n))).first()
    if user and not user.phone_verified:
        send_otp(user)
    # Réponse générique quoi qu'il arrive (anti-énumération).


def request_password_reset_sms(phone):
    """Envoie un code SMS de réinitialisation du mot de passe (par téléphone)."""
    from ..validation import normalize_phone

    phone_n = normalize_phone(phone)
    user = User.query.filter(User.phone.in_(_phone_candidates(phone_n))).first()
    if user and user.active:
        send_otp(user)  # réutilise l'infra OTP (génère + envoie un code)
    # Réponse générique (anti-énumération).


def reset_password_sms(phone, code, new_password):
    """Vérifie le code SMS et fixe le nouveau mot de passe. Retourne l'utilisateur."""
    from flask import current_app

    from ..validation import normalize_phone

    phone_n = normalize_phone(phone)
    user = User.query.filter(User.phone.in_(_phone_candidates(phone_n))).first()
    if not user:
        raise AuthError("Compte introuvable pour ce numéro.")
    if not user.otp_hash or not user.otp_expires_at or datetime.utcnow() > user.otp_expires_at:
        raise ValidationError("Code expiré. Demandez un nouveau code.")
    if (user.otp_attempts or 0) >= current_app.config["OTP_MAX_ATTEMPTS"]:
        raise ValidationError("Trop de tentatives. Demandez un nouveau code.")
    if not verify_password(code, user.otp_hash):
        user.otp_attempts = (user.otp_attempts or 0) + 1
        db.session.commit()
        raise AuthError("Code de vérification incorrect.")

    user.password_hash = hash_password(new_password)
    user.phone_verified = True  # une réinitialisation par SMS confirme aussi le numéro
    user.otp_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    db.session.commit()
    log.info("Mot de passe réinitialisé par SMS pour le compte #%s", user.id)
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


def delete_own_account(user_id):
    """Droit à l'effacement : anonymise les alertes du citoyen puis supprime son compte.

    On conserve les incidents (utilité de sécurité publique) mais on retire toute
    donnée personnelle (nom, téléphone, lien au compte).
    """
    from ..models import Alert

    user = User.query.get(user_id)
    if not user:
        raise AuthError("Compte introuvable.")
    Alert.query.filter_by(reporter_id=user.id).update(
        {"reporter_id": None,
         "reporter_name": "Citoyen (compte supprimé)",
         "reporter_phone": None},
        synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    log.info("Compte #%s supprimé (droit à l'effacement).", user_id)


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
