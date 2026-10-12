"""Endpoint de génération de rapports PDF."""
from flask import Blueprint, Response, request

from ..errors import ApiError
from ..security import require_auth
from ..services import audit
from ..services import reports as reports_service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")

VALID_PERIODS = {"today", "month", "year", "all"}


@bp.get("/pdf")
@require_auth(roles=["operator", "supervisor", "admin"])
def report_pdf():
    period = request.args.get("period", "all")
    if period not in VALID_PERIODS:
        period = "all"
    if not reports_service.REPORTLAB_AVAILABLE:
        raise ApiError(
            "Génération PDF indisponible : installez reportlab (pip install reportlab).",
            status_code=501, code="pdf_unavailable",
        )
    pdf = reports_service.generate_pdf(period)
    audit.record("report_generated", detail=f"Rapport PDF · période {period}")
    filename = f"safecity_rapport_{period}.pdf"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.get("/communes")
@require_auth(roles=["operator", "supervisor", "admin"])
def report_communes():
    """Rapport PDF des zones à risque par commune (aide à l'affectation des patrouilles)."""
    try:
        days = max(1, min(int(request.args.get("days", 30)), 730))
    except ValueError:
        days = 30
    if not reports_service.REPORTLAB_AVAILABLE:
        raise ApiError(
            "Génération PDF indisponible : installez reportlab (pip install reportlab).",
            status_code=501, code="pdf_unavailable",
        )
    pdf = reports_service.generate_communes_pdf(days)
    audit.record("report_generated", detail=f"Rapport zones à risque · {days} jours")
    return Response(
        pdf, mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="safecity_zones_a_risque_{days}j.pdf"'},
    )
