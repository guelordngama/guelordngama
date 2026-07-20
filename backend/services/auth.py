"""Service d'authentification : inscription des citoyens.

La connexion (login) reste gérée dans `api/auth.py` ; ce module porte la logique
métier de création de compte citoyen, dont la vérification d'unicité du numéro
de téléphone.
"""
import logging

from ..errors import ConflictError
from ..extensions import db
from ..models import User
from ..security import hash_password

log = logging.getLogger("safecity")


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
    digits = phone.lstrip("+")
    candidates = {phone, digits, "+" + digits}
    if User.query.filter(User.phone.in_(candidates)).first():
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
