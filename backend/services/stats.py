"""Service de statistiques pour le tableau de bord.

Calculs agrégés en SQL (GROUP BY) plutôt qu'en Python pour rester performant
quand le volume d'alertes augmente. Résultat mis en cache quelques secondes.
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
        return _CACHE["data"]

    total = db.session.query(func.count(Alert.id)).scalar() or 0
    active = (
        db.session.query(func.count(Alert.id))
        .filter(Alert.status != "cloturee")
        .scalar()
        or 0
    )

    today = datetime.utcnow().date()
    today_count = (
        db.session.query(func.count(Alert.id))
        .filter(func.date(Alert.created_at) == today)
        .scalar()
        or 0
    )

    by_type = {t: 0 for t in DANGER_TYPES}
    for type_, count in db.session.query(Alert.type, func.count(Alert.id)).group_by(Alert.type):
        by_type[type_] = count

    zones = (
        db.session.query(Alert.neighborhood, func.count(Alert.id).label("c"))
        .group_by(Alert.neighborhood)
        .order_by(func.count(Alert.id).desc())
        .limit(5)
        .all()
    )
    dangerous_zones = [{"zone": z or "Inconnu", "count": c} for z, c in zones]

    last = Alert.query.order_by(Alert.created_at.desc()).first()

    data = {
        "today_count": today_count,
        "active_count": active,
        "total_count": total,
        "by_type": by_type,
        "dangerous_zones": dangerous_zones,
        "last_alert": last.to_dict() if last else None,
    }
    _CACHE.update(ts=now, data=data)
    return data


def invalidate_cache():
    _CACHE.update(ts=0.0, data=None)
