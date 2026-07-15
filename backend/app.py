"""Application SafeCity : API Flask + temps réel Socket.IO.

Flux principal :
  1. Le citoyen envoie une alerte    -> POST /api/alerts
  2. Le backend classe l'incident (IA) et calcule la distance d'intervention
  3. Une notification temps réel est diffusée au centre de surveillance
  4. L'opérateur assigne une équipe   -> POST /api/alerts/<id>/assign
  5. L'opérateur clôture l'alerte      -> POST /api/alerts/<id>/close
"""
import base64
import os
import uuid
from datetime import datetime

from flask import (
    Flask,
    g,
    jsonify,
    request,
    send_from_directory,
)
from flask_cors import CORS
from flask_socketio import SocketIO, join_room

from .ai.classifier import get_classifier
from .auth import generate_token, hash_password, require_auth, verify_password
from .config import get_config
from .geo import compute_intervention, reverse_geocode
from .models import ALERT_STATUSES, DANGER_TYPES, Alert, Team, User, db

# `threading` fonctionne partout sans dépendance native ; en production on peut
# passer à eventlet/gevent via la variable d'environnement SAFECITY_ASYNC_MODE.
ASYNC_MODE = os.environ.get("SAFECITY_ASYNC_MODE", "threading")

socketio = SocketIO(cors_allowed_origins="*", async_mode=ASYNC_MODE)


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config or get_config())
    CORS(app)

    db.init_app(app)
    socketio.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_defaults()
        get_classifier()  # entraîne le modèle IA une fois au démarrage

    _register_routes(app)
    _register_socket_events()
    return app


# --------------------------------------------------------------------------- #
# Données de départ (équipes + compte opérateur de démonstration)
# --------------------------------------------------------------------------- #
def _seed_defaults():
    if Team.query.count() == 0:
        db.session.add_all(
            [
                Team(name="Patrouille Avenue Lumumba", patrol_lat=-4.3217, patrol_lng=15.3125, status="available"),
                Team(name="Patrouille Centre-Ville", patrol_lat=-4.3050, patrol_lng=15.3080, status="available"),
                Team(name="Patrouille Kenya", patrol_lat=-4.3400, patrol_lng=15.3300, status="available"),
            ]
        )
    if User.query.filter_by(role="operator").count() == 0:
        db.session.add(
            User(
                name="Opérateur Mairie",
                email="operateur@safecity.local",
                role="operator",
                password_hash=hash_password("safecity123"),
            )
        )
    db.session.commit()


# --------------------------------------------------------------------------- #
# Routes HTTP
# --------------------------------------------------------------------------- #
def _register_routes(app):

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

    @app.get("/api/meta")
    def meta():
        """Métadonnées utiles au front (types de danger, statuts)."""
        return jsonify({"danger_types": DANGER_TYPES, "statuses": ALERT_STATUSES})

    # ---- Fichiers envoyés (photos / audio) ----
    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_DIR"], filename)

    # ---- Authentification opérateur ----
    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not verify_password(password, user.password_hash):
            return jsonify({"error": "Identifiants invalides"}), 401
        return jsonify({"token": generate_token(user), "user": user.to_dict()})

    # ---- Création d'une alerte (citoyen) ----
    @app.post("/api/alerts")
    def create_alert():
        data = request.get_json(silent=True) or {}

        # Validation des coordonnées GPS.
        try:
            lat = float(data["lat"])
            lng = float(data["lng"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Coordonnées GPS (lat, lng) requises"}), 400

        declared_type = (data.get("type") or "autre").lower()
        if declared_type not in DANGER_TYPES:
            declared_type = "autre"
        description = (data.get("description") or "").strip()

        # 1) Classification IA (catégorie + urgence).
        ai = get_classifier().classify(description, declared_type)

        # 2) Quartier / adresse.
        neighborhood, address = reverse_geocode(lat, lng)
        neighborhood = data.get("neighborhood") or neighborhood
        address = data.get("address") or address

        # 3) Enregistrement des pièces jointes (base64 -> fichier).
        photo_path = _save_data_url(data.get("photo"), app.config["UPLOAD_DIR"])
        audio_path = _save_data_url(data.get("audio"), app.config["UPLOAD_DIR"])

        # 4) Distance / temps d'intervention depuis la patrouille par défaut.
        dist, eta_moto, eta_walk = compute_intervention(
            app.config["DEFAULT_PATROL_LAT"], app.config["DEFAULT_PATROL_LNG"], lat, lng
        )

        alert = Alert(
            type=declared_type,
            description=description,
            lat=lat,
            lng=lng,
            address=address,
            neighborhood=neighborhood,
            photo_path=photo_path,
            audio_path=audio_path,
            urgency=ai["urgency"],
            ai_score=ai["score"],
            ai_category=ai["category"],
            status="active",
            distance_m=dist,
            eta_moto_min=eta_moto,
            eta_walk_min=eta_walk,
            reporter_id=data.get("reporter_id"),
        )
        db.session.add(alert)
        db.session.commit()

        payload = alert.to_dict()
        # 5) Diffusion temps réel au centre de surveillance.
        socketio.emit("new_alert", payload, room=app.config["SURVEILLANCE_ROOM"])
        return jsonify(payload), 201

    # ---- Liste des alertes (filtrable) ----
    @app.get("/api/alerts")
    def list_alerts():
        query = Alert.query
        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)
        alerts = query.order_by(Alert.created_at.desc()).limit(200).all()
        return jsonify([a.to_dict() for a in alerts])

    @app.get("/api/alerts/<int:alert_id>")
    def get_alert(alert_id):
        alert = Alert.query.get_or_404(alert_id)
        return jsonify(alert.to_dict())

    # ---- Tableau de bord (statistiques) ----
    @app.get("/api/stats")
    def stats():
        today = datetime.utcnow().date()
        all_alerts = Alert.query.all()
        today_alerts = [a for a in all_alerts if a.created_at and a.created_at.date() == today]
        active = [a for a in all_alerts if a.status != "cloturee"]

        # Répartition par type (pour Qt Charts).
        by_type = {t: 0 for t in DANGER_TYPES}
        for a in all_alerts:
            by_type[a.type] = by_type.get(a.type, 0) + 1

        # Zones les plus signalées.
        by_zone = {}
        for a in all_alerts:
            key = a.neighborhood or "Inconnu"
            by_zone[key] = by_zone.get(key, 0) + 1
        dangerous_zones = sorted(by_zone.items(), key=lambda kv: kv[1], reverse=True)[:5]

        last = max(all_alerts, key=lambda a: a.created_at) if all_alerts else None
        return jsonify(
            {
                "today_count": len(today_alerts),
                "active_count": len(active),
                "total_count": len(all_alerts),
                "by_type": by_type,
                "dangerous_zones": [{"zone": z, "count": c} for z, c in dangerous_zones],
                "last_alert": last.to_dict() if last else None,
            }
        )

    # ---- Équipes ----
    @app.get("/api/teams")
    def list_teams():
        return jsonify([t.to_dict() for t in Team.query.all()])

    # ---- Assignation d'une équipe (opérateur) ----
    @app.post("/api/alerts/<int:alert_id>/assign")
    @require_auth(roles=["operator", "admin"])
    def assign_team(alert_id):
        data = request.get_json(silent=True) or {}
        alert = Alert.query.get_or_404(alert_id)
        team = Team.query.get_or_404(int(data.get("team_id", 0)))

        alert.assigned_team_id = team.id
        alert.status = "assignee"
        # Recalcule la distance depuis la position réelle de l'équipe.
        dist, eta_moto, eta_walk = compute_intervention(
            team.patrol_lat, team.patrol_lng, alert.lat, alert.lng
        )
        alert.distance_m, alert.eta_moto_min, alert.eta_walk_min = dist, eta_moto, eta_walk
        team.status = "busy"
        db.session.commit()

        payload = alert.to_dict()
        socketio.emit("alert_updated", payload, room=app.config["SURVEILLANCE_ROOM"])
        return jsonify(payload)

    # ---- Clôture d'une alerte (opérateur) ----
    @app.post("/api/alerts/<int:alert_id>/close")
    @require_auth(roles=["operator", "admin"])
    def close_alert(alert_id):
        alert = Alert.query.get_or_404(alert_id)
        alert.status = "cloturee"
        alert.closed_at = datetime.utcnow()
        if alert.assigned_team:
            alert.assigned_team.status = "available"
        db.session.commit()

        payload = alert.to_dict()
        socketio.emit("alert_updated", payload, room=app.config["SURVEILLANCE_ROOM"])
        return jsonify(payload)


# --------------------------------------------------------------------------- #
# Événements Socket.IO
# --------------------------------------------------------------------------- #
def _register_socket_events():

    @socketio.on("connect")
    def on_connect():
        # Chaque client (poste opérateur) rejoint la salle de surveillance.
        join_room(get_config().SURVEILLANCE_ROOM)
        socketio.emit("connected", {"message": "Connecté au centre SafeCity"})


# --------------------------------------------------------------------------- #
# Utilitaire : décodage d'une "data URL" base64 vers un fichier
# --------------------------------------------------------------------------- #
def _save_data_url(data_url, upload_dir):
    """Enregistre une chaîne base64 (data:<mime>;base64,....) en fichier.

    Retourne le nom de fichier relatif, ou None si l'entrée est vide/invalide.
    """
    if not data_url or not isinstance(data_url, str) or "," not in data_url:
        return None
    try:
        header, encoded = data_url.split(",", 1)
        ext = "bin"
        if "image/" in header:
            ext = header.split("image/")[1].split(";")[0]
        elif "audio/" in header:
            ext = header.split("audio/")[1].split(";")[0].split("/")[-1]
        filename = f"{uuid.uuid4().hex}.{ext}"
        with open(os.path.join(upload_dir, filename), "wb") as fh:
            fh.write(base64.b64decode(encoded))
        return filename
    except (ValueError, base64.binascii.Error, OSError):
        return None


# Instance module-level pour `flask run` et Waitress.
app = create_app()


if __name__ == "__main__":
    # Serveur de développement avec support temps réel.
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
