"""Conservation des données : purge des alertes clôturées anciennes.

Conformité : les données personnelles ne doivent pas être conservées
indéfiniment. Cette purge supprime les alertes clôturées au-delà de la durée
de conservation configurée (`SAFECITY_RETENTION_DAYS`), ainsi que leurs
fichiers joints (photo/audio).
"""
import logging
import os
from datetime import datetime, timedelta

from flask import current_app

from ..extensions import db
from ..models import Alert

log = logging.getLogger("safecity")


def _delete_upload(path):
    if not path:
        return
    try:
        full = os.path.join(current_app.config["UPLOAD_DIR"], path)
        if os.path.isfile(full):
            os.remove(full)
    except Exception as e:  # pragma: no cover
        log.warning("Fichier joint non supprimé (%s) : %s", path, e)


def purge_old_alerts(days=None):
    """Supprime les alertes clôturées plus anciennes que `days`. Retourne le nombre."""
    days = days if days is not None else current_app.config["RETENTION_DAYS"]
    cutoff = datetime.utcnow() - timedelta(days=int(days))
    old = (Alert.query
           .filter(Alert.status == "cloturee",
                   Alert.closed_at.isnot(None),
                   Alert.closed_at < cutoff)
           .all())
    count = 0
    for a in old:
        _delete_upload(a.photo_path)
        _delete_upload(a.audio_path)
        db.session.delete(a)
        count += 1
    db.session.commit()
    log.info("Purge de conservation : %s alerte(s) supprimée(s) (> %s jours).", count, days)
    return count
