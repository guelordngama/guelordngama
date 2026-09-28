"""Sécurité & traçabilité : vue d'ensemble pour le centre de commandement.

Expose les mécanismes réellement en place (authentification, rôles, protection
des données, résilience) et quelques indicateurs d'activité. Aucune donnée
personnelle n'est renvoyée en clair (téléphones masqués).
"""
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify
from sqlalchemy import func

from ..extensions import db
from ..models import ROLE_PERMISSIONS, ROLES, Alert, AuditLog, User
from ..security import UPLOAD_TTL_S, require_auth
from ..services.alerts import ROLE_LABELS

bp = Blueprint("security", __name__, url_prefix="/api/security")

PERMISSION_LABELS = {
    "view": "Consulter les alertes",
    "assign": "Affecter agents / patrouilles",
    "close": "Clôturer, classer fausse alerte",
    "manage_agents": "Gérer les agents",
    "manage_users": "Gérer les comptes",
    "settings": "Paramètres du système",
    "reports": "Rapports et exports",
}

# Ce que chaque rôle fait concrètement (gouvernance / responsabilités).
ROLE_DUTIES = {
    "citizen": "Déclenche une alerte (type, GPS, photo/vocal) et suit SON dossier "
               "par référence. Ne voit aucune autre alerte.",
    "agent": "Reçoit ses interventions, partage sa position, accepte puis termine "
             "l'intervention sur le terrain.",
    "operator": "Qualifie les alertes, affecte l'agent le plus proche, suit le trajet, "
                "clôture ou classe en fausse alerte (motif obligatoire).",
    "supervisor": "Contrôle l'activité : consulte le journal d'audit, annule une "
                  "qualification erronée, gère les agents, produit les rapports.",
    "admin": "Administre la plateforme : comptes, paramètres, sauvegardes, "
             "conservation des données.",
}


def _mask_phone(phone):
    if not phone:
        return "—"
    digits = str(phone)
    return digits[:4] + "•" * max(0, len(digits) - 6) + digits[-2:]


@bp.get("/overview")
@require_auth(roles=["operator", "supervisor", "admin"])
def overview():
    cfg = current_app.config
    now = datetime.utcnow()
    day, month = now - timedelta(hours=24), now - timedelta(days=30)

    counts = dict(db.session.query(User.role, func.count(User.id))
                  .filter(User.active.is_(True)).group_by(User.role).all())

    def audit_count(action, since):
        return AuditLog.query.filter(AuditLog.action == action,
                                     AuditLog.created_at >= since).count()

    repeat = (db.session.query(Alert.reporter_phone, Alert.reporter_name,
                               func.count(Alert.id).label("n"))
              .filter(Alert.false_alarm.is_(True), Alert.reporter_phone.isnot(None))
              .group_by(Alert.reporter_phone, Alert.reporter_name)
              .having(func.count(Alert.id) >= 2)
              .order_by(func.count(Alert.id).desc()).limit(10).all())

    total_30 = Alert.query.filter(Alert.created_at >= month).count()
    false_30 = Alert.query.filter(Alert.created_at >= month,
                                  Alert.false_alarm.is_(True)).count()

    return jsonify({
        "generated_at": now.isoformat() + "Z",
        "viewer_role": g.user.get("role"),
        "authentication": {
            "password_hashing": "bcrypt (sel unique par mot de passe)",
            "token": "JWT signé HS256",
            "token_hours": cfg["JWT_EXPIRES_HOURS"],
            "login_rate": f"{cfg['LOGIN_RATE_MAX']} essais / {cfg['LOGIN_RATE_WINDOW'] // 60} min",
            "otp": f"Code SMS à {cfg['OTP_LENGTH']} chiffres, valable {cfg['OTP_TTL_MIN']} min, "
                   f"{cfg['OTP_MAX_ATTEMPTS']} essais max",
            "inactive_accounts_blocked": True,
        },
        "roles": [{
            "role": r,
            "label": ROLE_LABELS.get(r, r),
            "users": counts.get(r, 0),
            "permissions": [PERMISSION_LABELS.get(p, p) for p in ROLE_PERMISSIONS.get(r, [])],
            "duties": ROLE_DUTIES.get(r, ""),
        } for r in ROLES],
        "data_protection": {
            "staff_only_data": "Nom, téléphone et GPS des citoyens réservés au personnel authentifié",
            "public_tracking": "Le citoyen suit son dossier par référence, sans aucune donnée personnelle",
            "media": f"Photos / vocaux / vidéos servis par liens signés, valables {UPLOAD_TTL_S // 3600} h",
            "realtime": "Flux temps réel réservé au personnel (jeton vérifié à la connexion)",
            "retention_days": cfg.get("RETENTION_DAYS"),
            "transport": "HTTPS (TLS Let's Encrypt) en production",
            "consent": "Consentement à la politique de confidentialité enregistré",
        },
        "resilience": {
            "backups": "Sauvegarde PostgreSQL automatique (toutes les 24 h, 14 copies)",
            "restore": "Restauration scriptée (deploy/restore.sh)",
            "offline_citizen": "Alerte mise en file sur le téléphone si le réseau tombe, "
                               "renvoyée automatiquement",
            "operator_fallback": "Rafraîchissement périodique si le temps réel est coupé",
            "health": "Point de contrôle /api/health pour la supervision",
        },
        "activity": {
            "logins_24h": audit_count("login", day),
            "failed_logins_24h": audit_count("login_failed", day),
            "audit_entries_24h": AuditLog.query.filter(AuditLog.created_at >= day).count(),
            "alerts_30d": total_30,
            "false_alarms_30d": false_30,
            "false_alarm_rate_30d": round(100.0 * false_30 / total_30, 1) if total_30 else 0.0,
        },
        "repeat_false_reporters": [
            {"phone": _mask_phone(p), "name": n or "Citoyen", "count": c} for p, n, c in repeat
        ],
    })
