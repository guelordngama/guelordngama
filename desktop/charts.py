"""Fabriques de graphiques Qt Charts stylés pour le thème sombre.

Importé de façon défensive : si QtCharts est absent, les fonctions renvoient un
simple libellé de repli plutôt que de planter l'application.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QLabel

import theme

try:
    from PySide6.QtCharts import (
        QBarCategoryAxis,
        QBarSeries,
        QBarSet,
        QChart,
        QChartView,
        QPieSeries,
        QValueAxis,
    )

    CHARTS_AVAILABLE = True
except Exception:  # pragma: no cover
    CHARTS_AVAILABLE = False


def _fallback(msg="Graphiques indisponibles"):
    lbl = QLabel(msg)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setObjectName("muted")
    return lbl


def _style_chart(chart):
    chart.setBackgroundBrush(QColor(theme.PANEL))
    chart.setBackgroundRoundness(0)
    chart.setPlotAreaBackgroundVisible(False)
    chart.legend().setVisible(False)
    chart.setTitleBrush(QColor(theme.TEXT))
    chart.setAnimationOptions(QChart.SeriesAnimations)


def bar_chart(data: dict, color=theme.ACCENT, height=240):
    """Histogramme vertical à partir d'un dict {catégorie: valeur}."""
    if not CHARTS_AVAILABLE:
        return _fallback()

    bar_set = QBarSet("")
    bar_set.setColor(QColor(color))
    bar_set.setBorderColor(QColor(color))
    categories = list(data.keys())
    for cat in categories:
        bar_set.append(float(data[cat]))

    series = QBarSeries()
    series.append(bar_set)
    series.setLabelsVisible(False)

    chart = QChart()
    chart.addSeries(series)
    _style_chart(chart)

    axis_x = QBarCategoryAxis()
    axis_x.append([str(c).capitalize() for c in categories])
    axis_x.setLabelsColor(QColor(theme.MUTED))
    axis_x.setGridLineVisible(False)
    axis_x.setLinePenColor(QColor(theme.BORDER))
    chart.addAxis(axis_x, Qt.AlignBottom)
    series.attachAxis(axis_x)

    axis_y = QValueAxis()
    axis_y.setLabelFormat("%d")
    axis_y.setLabelsColor(QColor(theme.MUTED))
    axis_y.setGridLinePen(QColor(theme.BORDER))
    max_val = int(max(data.values())) if data and max(data.values()) > 0 else 1
    axis_y.setRange(0, max_val)
    # Ticks entiers uniquement (évite les libellés "0" répétés).
    axis_y.setTickCount(min(max_val + 1, 6))
    chart.addAxis(axis_y, Qt.AlignLeft)
    series.attachAxis(axis_y)

    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    view.setMinimumHeight(height)
    view.setStyleSheet("background: transparent; border: none;")
    return view


def donut_chart(data: dict, colors=None, height=240):
    """Diagramme en anneau (répartition)."""
    if not CHARTS_AVAILABLE:
        return _fallback()

    series = QPieSeries()
    series.setHoleSize(0.55)
    palette = colors or [
        theme.ACCENT, theme.ACCENT_2, "#f97316", "#ef4444", "#a78bfa", "#22c55e",
    ]
    for i, (label, value) in enumerate(data.items()):
        if value <= 0:
            continue
        sl = series.append(f"{label} ({value})", float(value))
        sl.setColor(QColor(palette[i % len(palette)]))
        sl.setLabelVisible(False)
        sl.setBorderColor(QColor(theme.PANEL))

    chart = QChart()
    chart.addSeries(series)
    _style_chart(chart)
    chart.legend().setVisible(True)
    chart.legend().setAlignment(Qt.AlignRight)
    chart.legend().setLabelColor(QColor(theme.MUTED))

    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    view.setMinimumHeight(height)
    view.setStyleSheet("background: transparent; border: none;")
    return view
