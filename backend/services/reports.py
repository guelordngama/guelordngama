"""Génération de rapports PDF (synthèse des alertes).

Utilise reportlab si disponible. L'import est défensif : si reportlab n'est pas
installé, l'endpoint renvoie 501 avec un message clair plutôt que de planter.
"""
import io
from datetime import datetime

from sqlalchemy import func

from ..extensions import db
from ..models import DANGER_TYPES, Alert
from . import stats as stats_service

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except Exception:  # pragma: no cover
    REPORTLAB_AVAILABLE = False

PERIOD_LABELS = {
    "today": "Aujourd'hui",
    "month": "Ce mois-ci",
    "year": "Cette année",
    "all": "Depuis le début",
}

URGENCY_LABELS = {"faible": "Faible", "moyenne": "Moyen", "haute": "Élevé", "critique": "Critique"}
STATUS_LABELS = {"active": "En cours", "assignee": "Affectée", "cloturee": "Résolue"}

# Palette (cohérente avec l'interface).
_NAVY = None  # défini après import conditionnel


def _period_filter(query, period):
    now = datetime.utcnow()
    if period == "today":
        return query.filter(func.date(Alert.created_at) == now.date())
    if period == "month":
        return query.filter(
            func.extract("year", Alert.created_at) == now.year,
            func.extract("month", Alert.created_at) == now.month,
        )
    if period == "year":
        return query.filter(func.extract("year", Alert.created_at) == now.year)
    return query


def generate_pdf(period="all"):
    """Retourne les octets d'un PDF de synthèse pour la période demandée."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab n'est pas installé (pip install reportlab).")

    navy = colors.HexColor("#0b1220")
    accent = colors.HexColor("#3d8bff")
    grey = colors.HexColor("#8595b4")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title="Rapport SafeCity",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=navy, fontSize=22)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=accent, fontSize=13)
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, textColor=grey, fontSize=9)

    elems = []
    elems.append(Paragraph("SafeCity — Rapport d'activité", h1))
    elems.append(Paragraph(
        f"Période : {PERIOD_LABELS.get(period, period)} · "
        f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", small))
    elems.append(Spacer(1, 0.5 * cm))

    # --- Indicateurs clés ---
    stats = stats_service.compute_stats(use_cache=False)
    rt = stats.get("avg_response_min")
    kpi_rows = [
        ["Total signalements", str(stats["total_count"])],
        ["Alertes en cours", str(stats["in_progress_count"])],
        ["Interventions clôturées", str(stats["resolved_count"])],
        ["Temps de réponse moyen", f"{rt} min" if rt is not None else "—"],
        ["Agents connectés", str(stats["agents_connected"])],
    ]
    elems.append(Paragraph("Indicateurs clés", h2))
    elems.append(_kv_table(kpi_rows, accent, navy))
    elems.append(Spacer(1, 0.5 * cm))

    # --- Répartition par type ---
    base = _period_filter(Alert.query, period)
    period_alerts = base.order_by(Alert.created_at.desc()).all()
    by_type = {t: 0 for t in DANGER_TYPES}
    by_zone = {}
    for a in period_alerts:
        by_type[a.type] = by_type.get(a.type, 0) + 1
        z = a.neighborhood or "Inconnu"
        by_zone[z] = by_zone.get(z, 0) + 1

    elems.append(Paragraph("Incidents par type", h2))
    elems.append(_kv_table([[t.capitalize(), str(c)] for t, c in by_type.items()], accent, navy))
    elems.append(Spacer(1, 0.4 * cm))

    top_zones = sorted(by_zone.items(), key=lambda kv: kv[1], reverse=True)[:8]
    if top_zones:
        elems.append(Paragraph("Incidents par commune (top 8)", h2))
        elems.append(_kv_table([[z, str(c)] for z, c in top_zones], accent, navy))
        elems.append(Spacer(1, 0.5 * cm))

    # --- Détail des alertes ---
    elems.append(Paragraph(f"Détail des alertes ({len(period_alerts)})", h2))
    header = ["Heure", "Type", "Quartier", "Urgence", "Statut"]
    data = [header]
    for a in period_alerts[:60]:
        data.append([
            a.created_at.strftime("%d/%m %H:%M") if a.created_at else "—",
            a.type.capitalize(),
            a.neighborhood or "—",
            URGENCY_LABELS.get(a.urgency, a.urgency or "—"),
            STATUS_LABELS.get(a.status, a.status),
        ])
    table = Table(data, repeatRows=1, colWidths=[3 * cm, 3 * cm, 4 * cm, 2.6 * cm, 2.6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2fb")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elems.append(table)
    if len(period_alerts) > 60:
        elems.append(Spacer(1, 0.2 * cm))
        elems.append(Paragraph(f"… et {len(period_alerts) - 60} autres.", small))

    elems.append(Spacer(1, 0.8 * cm))
    elems.append(Paragraph(
        "Document généré automatiquement par SafeCity. Confidentiel — usage interne.", small))

    doc.build(elems)
    return buf.getvalue()


def _kv_table(rows, accent, navy):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle

    t = Table(rows, colWidths=[8 * cm, 4 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), navy),
        ("TEXTCOLOR", (1, 0), (1, -1), accent),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f2f5fb")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#dbe2f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t
