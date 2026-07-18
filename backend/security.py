"""Sécurité SafeCity : hachage bcrypt, jetons JWT, contrôle d'accès,
limitation du débit (anti force brute) et validation des fichiers envoyés.
"""
import base64
import binascii
import datetime
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import wraps

import bcrypt
import jwt
from flask import current_app, g, request

from .errors import AuthError, ForbiddenError, RateLimitError, ValidationError

# Garde-fou : le paquet PyPI "jwt" (différent de PyJWT) n'a pas jwt.encode et
# provoquerait une erreur 500 obscure. On échoue tôt avec un message clair.
if not hasattr(jwt, "encode"):
    raise ImportError(
        "Le paquet 'jwt' importé n'est pas PyJWT (jwt.encode introuvable). "
        "Corrigez avec :\n    pip uninstall -y jwt PyJWT && pip install PyJWT"
    )


# --------------------------------------------------------------------------- #
# Mots de passe
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# Jetons JWT
# --------------------------------------------------------------------------- #
def generate_token(user):
    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(user.id),  # PyJWT >= 2.10 exige un "sub" de type chaîne
        "uid": user.id,
        "role": user.role,
        "name": user.name,
        "iss": current_app.config["JWT_ISSUER"],
        "iat": now,
        "exp": now + datetime.timedelta(hours=current_app.config["JWT_EXPIRES_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET"],
        algorithms=["HS256"],
        issuer=current_app.config["JWT_ISSUER"],
        options={"require": ["exp", "sub"]},
    )


def _extract_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.args.get("token")


def require_auth(roles=None):
    """Décorateur exigeant un JWT valide, éventuellement un rôle précis.

    Place l'utilisateur décodé dans flask.g.user.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                raise AuthError("Authentification requise.")
            try:
                payload = decode_token(token)
            except jwt.ExpiredSignatureError:
                raise AuthError("Jeton expiré.")
            except jwt.InvalidTokenError:
                raise AuthError("Jeton invalide.")
            if roles and payload.get("role") not in roles:
                raise ForbiddenError("Accès refusé pour ce rôle.")
            g.user = payload
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Limitation du débit (in-memory, par IP + clé)
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Fenêtre glissante simple, thread-safe, sans dépendance externe.

    Suffisant pour un déploiement mono-processus. Pour plusieurs workers,
    remplacer par un backend Redis.
    """

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key, max_calls, window_seconds):
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_calls:
                retry = int(window_seconds - (now - q[0])) + 1
                return False, retry
            q.append(now)
            return True, 0


_rate_limiter = RateLimiter()


def rate_limit(max_calls, window_seconds, scope="default"):
    """Décorateur de limitation par IP cliente."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
            allowed, retry = _rate_limiter.check(f"{scope}:{ip}", max_calls, window_seconds)
            if not allowed:
                raise RateLimitError(
                    f"Trop de tentatives. Réessayez dans {retry} s.",
                    details={"retry_after": retry},
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Validation & enregistrement des fichiers (data URL base64)
# --------------------------------------------------------------------------- #
def save_data_url(data_url, kind):
    """Enregistre une data URL base64 en fichier après validation du type.

    `kind` vaut "image" ou "audio". Retourne le nom de fichier relatif, ou None
    si l'entrée est vide. Lève ValidationError si le type n'est pas autorisé.
    """
    if not data_url or not isinstance(data_url, str) or "," not in data_url:
        return None

    header, encoded = data_url.split(",", 1)
    upload_dir = current_app.config["UPLOAD_DIR"]
    if kind == "image":
        allowed = current_app.config["ALLOWED_IMAGE_EXT"]
        mime_prefix = "image/"
    else:
        allowed = current_app.config["ALLOWED_AUDIO_EXT"]
        mime_prefix = "audio/"

    ext = "bin"
    if mime_prefix in header:
        ext = header.split(mime_prefix, 1)[1].split(";")[0].split("/")[-1].lower()
    if ext == "jpeg":
        ext = "jpg"
    if ext not in allowed:
        raise ValidationError(f"Type de fichier non autorisé pour {kind} : .{ext}")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValidationError(f"Contenu {kind} invalide (base64).")

    max_bytes = current_app.config["MAX_CONTENT_LENGTH"]
    if len(raw) > max_bytes:
        raise ValidationError(f"Fichier {kind} trop volumineux.")

    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(upload_dir, filename), "wb") as fh:
        fh.write(raw)
    return filename
