"""Journal d'audit : enregistrement des actions sensibles.

L'appel est **best-effort** : un échec d'écriture du journal ne doit jamais
faire échouer la requête métier (on journalise l'incident et on continue).
"""
import logging

from flask import g, has_request_context, request

from ..extensions import db
from ..models import AuditLog

log = logging.getLogger("safecity")


def record(action, detail=None, user_id=None, user_name=None):
    """Enregistre une entrée d'audit.

    L'utilisateur et l'IP sont déduits du contexte de requête si disponibles ;
    `user_id` / `user_name` permettent de forcer des valeurs (ex. échec de
    connexion, où aucun JWT n'est présent).
    """
    try:
        ip = None
        if has_request_context():
            ip = request.headers.get(
                "X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
            claims = getattr(g, "user", None)
            if claims and user_id is None:
                user_id = claims.get("uid")
                user_name = user_name or claims.get("name")
        entry = AuditLog(
            action=action,
            detail=(str(detail)[:255] if detail else None),
            user_id=user_id,
            user_name=user_name,
            ip=ip,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:  # pragma: no cover - ne doit jamais casser la requête
        db.session.rollback()
        log.warning("Entrée d'audit non enregistrée (%s) : %s", action, e)
