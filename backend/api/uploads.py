"""Service des fichiers envoyés (photos / audio des alertes)."""
from flask import Blueprint, current_app, send_from_directory

bp = Blueprint("uploads", __name__)


@bp.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename)
