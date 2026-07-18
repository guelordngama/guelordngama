"""Service de statistiques pour le tableau de bord.

Calculs agrégés en SQL (GROUP BY) pour rester performant. Résultat mis en cache
quelques secondes pour absorber les rafales de requêtes.
"""
import time
from datetime import datetime

from sqlalchemy import func

from ..extensions import db
from ..models import DANGER_TYPES, Alert

_CACHE = {"ts": 0.0, "data": None}
_CACHE_TTL = 3.0  # secondes


def compute_stats(use_cache=True):
    now = time.time()
    if use_cache and _CACHE["data"] is not None and now - _CACHE["ts"] < _CACHE_TTL:
        return {**_CACHE["data"], "agents_connected": _agents_connected()}

    total = _scalar(db.session.query(func.count(Alert.id)))
    active = _scalar(
        db.session.query(func.count(Alert.id)).filter(Alert.status == "active")
    )
    assigned = _scalar(
        db.session.query(func.count(Alert.id)).filter(Alert.status == "assignee")
    )
    resolved = _scalar(
        db.session.query(func.count(Alert.id)).filter(Alert.status == "cloturee")
    )
    in_progress = active + assigned

    today = datetime.utcnow().date()
    today_count = _scalar(
        db.session.query(func.count(Alert.id)).filter(func.date(Alert.created_at) == today)
    )
    resolved_today = _scalar(
        db.session.query(func.count(Alert.id)).filter(
            Alert.status == "cloturee", func.date(Alert.closed_at) == today
        )
    )

    by_type = {t: 0 for t in DANGER_TYPES}
    for type_, count in db.session.query(Alert.type, func.count(Alert.id)).group_by(Alert.type):
        by_type[type_] = count

    zones = (
        db.session.query(Alert.neighborhood, func.count(Alert.id).label("c"))
        .group_by(Alert.neighborhood)
        .order_by(func.count(Alert.id).desc())
        .limit(8)
        .all()
    )
    by_commune = [{"zone": z or "Inconnu", "count": c} for z, c in zones]

    # Temps de réponse moyen (minutes) sur les alertes clôturées.
    avg_response_min = _avg_response_minutes()

    last = Alert.query.order_by(Alert.created_at.desc()).first()

    data = {
        "today_count": today_count,
        "active_count": in_progress,
        "in_progress_count": in_progress,
        "resolved_count": resolved,
        "resolved_today": resolved_today,
        "total_count": total,
        "avg_response_min": avg_response_min,
        "by_type": by_type,
        "dangerous_zones": by_commune,
        "by_commune": by_commune,
        "last_alert": last.to_dict() if last else None,
    }
    _CACHE.update(ts=now, data=data)
    return {**data, "agents_connected": _agents_connected()}


def _avg_response_minutes():
    rows = (
        db.session.query(Alert.created_at, Alert.closed_at)
        .filter(Alert.status == "cloturee", Alert.closed_at.isnot(None))
        .all()
    )
    if not rows:
        return None
    deltas = [(c - o).total_seconds() / 60.0 for o, c in rows if c and o]
    return round(sum(deltas) / len(deltas), 1) if deltas else None


def _agents_connected():
    # Import tardif pour éviter un cycle d'import.
    from ..realtime import connected_count

    return connected_count()


def _scalar(query):
    return query.scalar() or 0


def invalidate_cache():
    _CACHE.update(ts=0.0, data=None)
