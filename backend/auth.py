"""Authentification SafeCity : hachage bcrypt des mots de passe et jetons JWT.

Les endpoints sensibles (assignation d'équipe, clôture d'alerte, tableau de
bord) sont réservés aux opérateurs authentifiés.
"""
import datetime
from functools import wraps

import bcrypt
import jwt
from flask import current_app, g, jsonify, request


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_token(user):
    payload = {
        "sub": str(user.id),  # PyJWT >= 2.10 exige un "sub" de type chaîne
        "uid": user.id,
        "role": user.role,
        "name": user.name,
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(hours=current_app.config["JWT_EXPIRES_HOURS"]),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])


def _extract_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.args.get("token")


def require_auth(roles=None):
    """Décorateur : exige un JWT valide, éventuellement un rôle précis.

    Usage : @require_auth(roles=["operator", "admin"])
    Place l'utilisateur décodé dans flask.g.user.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"error": "Authentification requise"}), 401
            try:
                payload = decode_token(token)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Jeton expiré"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Jeton invalide"}), 401
            if roles and payload.get("role") not in roles:
                return jsonify({"error": "Accès refusé"}), 403
            g.user = payload
            return fn(*args, **kwargs)

        return wrapper

    return decorator
