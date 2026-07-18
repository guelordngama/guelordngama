"""Export des historiques d'alertes (CSV / Excel)."""
from flask import Blueprint, Response, request

from ..errors import ApiError
from ..security import require_auth
from ..services import export as export_service

bp = Blueprint("export", __name__, url_prefix="/api/export")

FILTER_KEYS = ("status", "type", "urgency", "neighborhood", "agent_id", "q",
               "date_from", "date_to")


def _filters():
    f = {k: request.args.get(k) for k in FILTER_KEYS if request.args.get(k)}
    if "agent_id" in f:
        try:
            f["agent_id"] = int(f["agent_id"])
        except ValueError:
            f.pop("agent_id")
    return f


@bp.get("/alerts.csv")
@require_auth(roles=["operator", "supervisor", "admin"])
def export_csv():
    data = export_service.to_csv(_filters())
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="safecity_alertes.csv"'})


@bp.get("/alerts.xlsx")
@require_auth(roles=["operator", "supervisor", "admin"])
def export_xlsx():
    if not export_service.OPENPYXL_AVAILABLE:
        raise ApiError("Export Excel indisponible : installez openpyxl.",
                       status_code=501, code="xlsx_unavailable")
    data = export_service.to_xlsx(_filters())
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="safecity_alertes.xlsx"'},
    )
