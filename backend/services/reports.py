"""Génération de rapports PDF (synthèse des alertes).

Utilise reportlab si disponible. L'import est défensif : si reportlab n'est pas
installé, l'endpoint renvoie 501 avec un message clair plutôt que de planter.
"""
import io
from datetime import datetime

from sqlalchemy import func

from ..extensions import db
from ..models import DANGER_TYPES, Alert, local_str
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
        elems.append(Paragraph("Incidents par quartier (top 8)", h2))
        elems.append(_kv_table([[z, str(c)] for z, c in top_zones], accent, navy))
        elems.append(Spacer(1, 0.5 * cm))

    # --- Détail des alertes ---
    elems.append(Paragraph(f"Détail des alertes ({len(period_alerts)})", h2))
    header = ["Heure", "Type", "Quartier", "Urgence", "Statut"]
    data = [header]
    for a in period_alerts[:60]:
        data.append([
            local_str(a.created_at, "%d/%m %H:%M") or "—",
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


def generate_communes_pdf(days=30):
    """Rapport par commune pour la mairie : classement des zones à risque,
    tranches horaires, carte de chaleur simplifiée et recommandations."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab n'est pas installé (pip install reportlab).")
    from reportlab.graphics.shapes import Circle, Drawing, Rect, String

    from . import risk as risk_service

    navy = colors.HexColor("#0b1220")
    accent = colors.HexColor("#3d8bff")
    grey = colors.HexColor("#8595b4")
    data = risk_service.communes_report(days)
    heat = risk_service.heatmap(days)
    days = data["days"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title="SafeCity — Zones à risque")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=navy, fontSize=21)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=accent, fontSize=13)
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, textColor=grey, fontSize=9)
    reco = ParagraphStyle("reco", parent=normal, fontSize=10, leading=14, leftIndent=10)

    elems = [Paragraph("SafeCity — Zones à risque par commune", h1),
             Paragraph(f"Mairie de Lubumbashi · {days} derniers jours · "
                       f"généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", small),
             Spacer(1, 0.4 * cm)]

    prev = data["previous_total"]
    delta = ""
    if prev:
        pct = round((data["total"] - prev) * 100 / prev)
        delta = f" ({'+' if pct > 0 else ''}{pct} % par rapport aux {days} jours précédents)"
    elems.append(Paragraph(
        f"<b>{data['total']}</b> incident(s) réel(s){delta}. Les doublons, fausses alertes et "
        "alertes annulées par les citoyens sont exclus du décompte.", normal))
    elems.append(Spacer(1, 0.4 * cm))

    elems.append(Paragraph("Recommandations pour l'affectation des patrouilles", h2))
    for r in data["recommendations"]:
        elems.append(Paragraph("• " + r, reco))
    elems.append(Spacer(1, 0.4 * cm))

    # --- Classement des communes ---
    elems.append(Paragraph("Classement des communes", h2))
    head = ["#", "Commune", "Incidents", "Part", "Urgents", "Pic horaire", "Tendance", "Risque"]
    rows = [head]
    risk_color = {"élevé": colors.HexColor("#fecaca"), "moyen": colors.HexColor("#fed7aa"),
                  "faible": colors.HexColor("#bbf7d0")}
    for r in data["communes"]:
        t = r["trend_pct"]
        rows.append([str(r["rank"]), r["commune"], str(r["count"]), f"{r['share_pct']} %",
                     str(r["urgent"]), risk_service.BAND_LABELS.get(r["peak_band"], "—").split(" (")[0],
                     "—" if t is None else f"{'+' if t > 0 else ''}{t} %", r["risk"].capitalize()])
    table = Table(rows, repeatRows=1, colWidths=[0.9 * cm, 3.4 * cm, 2.1 * cm, 1.8 * cm,
                                                  2 * cm, 2.8 * cm, 2.2 * cm, 2.2 * cm])
    style = [("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e8")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i, r in enumerate(data["communes"], 1):
        style.append(("BACKGROUND", (7, i), (7, i), risk_color[r["risk"]]))
    table.setStyle(TableStyle(style))
    elems += [table, Spacer(1, 0.5 * cm)]

    # --- Tranches horaires par commune ---
    elems.append(Paragraph("Incidents par tranche horaire", h2))
    brow = [["Commune"] + [lbl.split(" (")[0] for _k, lbl, _a, _b in risk_service.BANDS]]
    for r in data["communes"]:
        brow.append([r["commune"]] + [str(r["by_band"][k]) for k, *_ in risk_service.BANDS])
    bt = Table(brow, repeatRows=1)
    bt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e8"))]))
    elems += [bt, Spacer(1, 0.5 * cm)]

    # --- Quartiers les plus touchés ---
    hot = [r for r in data["communes"] if r["top_neighborhoods"]]
    if hot:
        elems.append(Paragraph("Quartiers les plus touchés", h2))
        hrows = [["Commune", "Quartiers (incidents)", "Type dominant"]]
        for r in hot:
            hrows.append([r["commune"],
                          ", ".join(f"{n['name']} ({n['count']})" for n in r["top_neighborhoods"]),
                          (r["top_type"] or "—").capitalize()])
        ht = Table(hrows, repeatRows=1, colWidths=[3.4 * cm, 10 * cm, 4 * cm])
        ht.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("FONTSIZE", (0, 0), (-1, -1), 9),
                                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e8"))]))
        elems += [ht, Spacer(1, 0.5 * cm)]

    # --- Carte de chaleur simplifiée (nuage de points) ---
    pts = heat["points"]
    if pts:
        W, H = 17.6 * cm, 8.5 * cm
        d = Drawing(W, H)
        d.add(Rect(0, 0, W, H, fillColor=colors.HexColor("#eef2fb"), strokeColor=colors.HexColor("#cbd5e8")))
        lats = [p["lat"] for p in pts]; lngs = [p["lng"] for p in pts]
        la0, la1, lo0, lo1 = min(lats), max(lats), min(lngs), max(lngs)
        span_la = max(la1 - la0, 0.004); span_lo = max(lo1 - lo0, 0.004)
        for p in pts:
            x = 0.6 * cm + (p["lng"] - lo0) / span_lo * (W - 1.2 * cm)
            y = 0.6 * cm + (p["lat"] - la0) / span_la * (H - 1.2 * cm)
            d.add(Circle(x, y, 0.28 * cm * (0.7 + 0.15 * p["w"]), strokeColor=None,
                         fillColor=colors.Color(0.86, 0.15, 0.15, alpha=0.22)))
        d.add(String(8, H - 12, "N ↑   (plus la tache est foncée, plus la zone est touchée)",
                     fontSize=7.5, fillColor=colors.HexColor("#475569")))
        elems.append(Paragraph("Carte de chaleur des incidents", h2))
        elems += [d, Spacer(1, 0.3 * cm)]
    if heat["hotspots"]:
        elems.append(Paragraph("Points chauds (zones d'environ 300 m)", h2))
        elems.append(Paragraph("<br/>".join(
            f"{i}. {h['label']} — {h['count']} incident(s)" for i, h in enumerate(heat["hotspots"][:5], 1)),
            normal))
    elems += [Spacer(1, 0.6 * cm), Paragraph(
        "Document généré automatiquement par SafeCity à partir des signalements citoyens. "
        "Aide à la décision : à croiser avec la connaissance du terrain. Confidentiel.", small)]
    doc.build(elems)
    return buf.getvalue()
