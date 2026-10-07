"""Endpoints des alertes : création (citoyen), consultation, affectation,
clôture (opérateur)."""
from flask import Blueprint, current_app, g, jsonify, request

from ..security import require_auth
from ..services import alerts as alerts_service
from ..services import audit
from ..services import stats as stats_service
from ..validation import validate_alert_payload, validate_team_id

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@bp.post("")
def create():
    data = validate_alert_payload(request.get_json(silent=True))
    payload = alerts_service.create_alert(data)
    stats_service.invalidate_cache()
    grouped = bool(payload.get("duplicate_of"))
    audit.record("alert_grouped" if grouped else "alert_created",
                 detail=f"{payload.get('type')} · réf. {payload.get('reference')}",
                 user_id=payload.get("reporter_id"),
                 user_name=payload.get("reporter_name") or "Citoyen",
                 role="citizen",
                 alert_id=payload.get("duplicate_of") if grouped else payload.get("id"))
    return jsonify(payload), 201


FILTER_KEYS = ("status", "type", "urgency", "neighborhood", "agent_id", "q",
               "date_from", "date_to", "false_alarm")


# Consultation réservée au personnel : ces données contiennent le nom, le
# téléphone et la position GPS des citoyens (le citoyen suit SON alerte via
# /track/<référence>, qui ne renvoie rien de personnel).
@bp.get("")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def list_():
    filters = {k: request.args.get(k) for k in FILTER_KEYS if request.args.get(k)}
    if "agent_id" in filters:
        try:
            filters["agent_id"] = int(filters["agent_id"])
        except ValueError:
            filters.pop("agent_id")
    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(
        current_app.config["ALERTS_MAX_PAGE_SIZE"],
        request.args.get("page_size", current_app.config["ALERTS_PAGE_SIZE"], type=int),
    )
    result = alerts_service.list_alerts(filters=filters, page=page, page_size=page_size)
    # Compatibilité : liste simple si ni pagination ni filtre de recherche.
    search_keys = {"page", "page_size", "q", "type", "urgency", "neighborhood",
                   "agent_id", "date_from", "date_to", "false_alarm"}
    if not (search_keys & set(request.args.keys())):
        return jsonify(result["items"])
    return jsonify(result)


@bp.get("/track/<ref>")
def track(ref):
    """Suivi citoyen par référence publique (ex. « SC-K7P2Q9 »). Public, mais ne
    renvoie que l'avancement du traitement — aucune donnée sensible."""
    status = alerts_service.track_alert(ref)
    if status is None:
        return jsonify({"error": {"message": "Référence introuvable"}}), 404
    return jsonify(status)


@bp.get("/<int:alert_id>")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def detail(alert_id):
    item = alerts_service.get_alert(alert_id).to_dict()
    return jsonify(alerts_service.attach_reporter_flags([item])[0])


@bp.post("/<int:alert_id>/assign")
@require_auth(roles=["operator", "admin"])
def assign(alert_id):
    team_id = validate_team_id(request.get_json(silent=True))
    payload = alerts_service.assign_team(alert_id, team_id)
    stats_service.invalidate_cache()
    audit.record("team_assigned", detail=(payload.get("assigned_team") or {}).get("name")
                 if isinstance(payload.get("assigned_team"), dict) else f"équipe #{team_id}",
                 alert_id=alert_id)
    return jsonify(payload)


@bp.post("/<int:alert_id>/close")
@require_auth(roles=["operator", "supervisor", "admin"])
def close(alert_id):
    payload = alerts_service.close_alert(alert_id)
    stats_service.invalidate_cache()
    audit.record("alert_closed", detail=_ref(payload), alert_id=alert_id)
    return jsonify(payload)


@bp.post("/<int:alert_id>/assign-agent")
@require_auth(roles=["operator", "supervisor", "admin"])
def assign_agent(alert_id):
    data = request.get_json(silent=True) or {}
    try:
        agent_id = int(data.get("agent_id"))
    except (TypeError, ValueError):
        from ..errors import ValidationError
        raise ValidationError("Le champ 'agent_id' (entier) est requis.")
    payload = alerts_service.assign_agent(alert_id, agent_id)
    stats_service.invalidate_cache()
    agent = payload.get("assigned_agent") or {}
    audit.record("agent_assigned", detail=f"{agent.get('name') or 'agent #%s' % agent_id} → {_ref(payload)}",
                 alert_id=alert_id)
    return jsonify(payload)


@bp.post("/<int:alert_id>/accept")
@require_auth(roles=["agent"])
def accept(alert_id):
    """L'agent assigné confirme qu'il se rend sur l'intervention (étape
    « Agent en route »). Réservé à l'agent : affecter une alerte reste le
    rôle exclusif du poste opérateur (POST /<id>/assign-agent)."""
    payload = alerts_service.accept_intervention(alert_id, g.user)
    stats_service.invalidate_cache()
    audit.record("intervention_accepted", detail=_ref(payload), alert_id=alert_id)
    return jsonify(payload)


@bp.post("/<int:alert_id>/arrived")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def arrived(alert_id):
    """L'agent (ou le centre, en son nom) signale son arrivée sur les lieux —
    étape « Sur place » de la progression de l'alerte."""
    payload = alerts_service.mark_arrived(alert_id, g.user)
    stats_service.invalidate_cache()
    audit.record("agent_arrived", detail=_ref(payload), alert_id=alert_id)
    return jsonify(payload)


@bp.post("/<int:alert_id>/complete")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def complete(alert_id):
    """L'agent termine (clôture) sa propre intervention."""
    payload = alerts_service.complete_intervention(alert_id, g.user)
    stats_service.invalidate_cache()
    audit.record("intervention_completed", detail=_ref(payload), alert_id=alert_id)
    return jsonify(payload)


# --------------------------------------------------------------------------- #
# Fausses alertes : qualification tracée (motif obligatoire). Un opérateur peut
# classer ; seul un superviseur / administrateur peut annuler (contrôle croisé).
# --------------------------------------------------------------------------- #
@bp.post("/<int:alert_id>/false-alarm")
@require_auth(roles=["operator", "supervisor", "admin"])
def mark_false_alarm(alert_id):
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    payload = alerts_service.mark_false_alarm(alert_id, reason, g.user.get("name"))
    stats_service.invalidate_cache()
    audit.record("false_alarm_marked", detail=f"{_ref(payload)} · motif : {reason}",
                 alert_id=alert_id)
    return jsonify(payload)


@bp.delete("/<int:alert_id>/false-alarm")
@require_auth(roles=["supervisor", "admin"])
def cancel_false_alarm(alert_id):
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    if len(reason) < 3:
        from ..errors import ValidationError
        raise ValidationError("Indiquez la raison de l'annulation.")
    payload = alerts_service.cancel_false_alarm(alert_id)
    stats_service.invalidate_cache()
    audit.record("false_alarm_cancelled", detail=f"{_ref(payload)} · raison : {reason}",
                 alert_id=alert_id)
    return jsonify(payload)


@bp.get("/<int:alert_id>/journal")
@require_auth(roles=["agent", "operator", "supervisor", "admin"])
def journal(alert_id):
    """Journal de l'intervention : chaque action, son auteur, son rôle, l'heure."""
    return jsonify(alerts_service.alert_journal(alert_id))


def _ref(payload):
    return payload.get("incident_number") or f"alerte #{payload.get('id')}"
