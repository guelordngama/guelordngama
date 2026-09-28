"""Service des fichiers envoyés (photos, vocaux, vidéos des alertes et messages).

Accès PROTÉGÉ : lien signé et non expiré (fourni dans les données réservées au
personnel), ou jeton du personnel dans l'en-tête Authorization. Sinon 403.
"""
import time

from flask import Blueprint, current_app, request, send_from_directory

from ..errors import ForbiddenError
from ..security import decode_token, verify_upload_signature

bp = Blueprint("uploads", __name__)

_STAFF = {"agent", "operator", "supervisor", "admin"}


def _staff_header_ok():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return False
    try:
        return decode_token(header[7:].strip()).get("role") in _STAFF
    except Exception:
        return False


@bp.get("/uploads/<path:filename>")
def uploaded_file(filename):
    exp, sig = request.args.get("exp"), request.args.get("sig")
    if not (verify_upload_signature(filename, exp, sig) or _staff_header_ok()):
        raise ForbiddenError("Lien de fichier invalide ou expiré.")
    resp = send_from_directory(current_app.config["UPLOAD_DIR"], filename)
    # Cache privé (jamais dans un proxy partagé), limité à la validité du lien.
    left = max(0, int(exp) - int(time.time())) if exp and exp.isdigit() else 0
    resp.headers["Cache-Control"] = f"private, max-age={min(left, 3600)}"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp
