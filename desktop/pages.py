"""Pages (vues) du poste opérateur SafeCity, empilées dans le QStackedWidget."""
import os

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import charts
import theme
from widgets import Badge, Card, StatCard

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView

    WEBENGINE_AVAILABLE = True
except Exception:  # pragma: no cover
    WEBENGINE_AVAILABLE = False


def _table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(False)
    return t


def _item(text, color=None, bold=False):
    it = QTableWidgetItem(str(text))
    if color:
        it.setForeground(QColor(color))
    return it


# --------------------------------------------------------------------------- #
# Tableau de bord
# --------------------------------------------------------------------------- #
class DashboardPage(QWidget):
    request_focus = Signal(int)
    go_to_map = Signal()

    def __init__(self):
        super().__init__()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(18)

        # Rangée de tuiles
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card_today = StatCard("🚨", "Alertes aujourd'hui", theme.ACCENT)
        self.card_progress = StatCard("⏳", "Alertes en cours", "#f97316")
        self.card_resolved = StatCard("✅", "Alertes résolues", "#22c55e")
        self.card_agents = StatCard("👮", "Agents connectés", theme.ACCENT_2)
        for c in (self.card_today, self.card_progress, self.card_resolved, self.card_agents):
            cards.addWidget(c)
        root.addLayout(cards)

        # Graphiques (2 colonnes)
        gr = QHBoxLayout()
        gr.setSpacing(16)
        self.card_types = Card("Répartition par type d'incident")
        self.card_zones = Card("Zones à risque (top communes)")
        self._types_holder = QVBoxLayout()
        self._zones_holder = QVBoxLayout()
        self.card_types.v.addLayout(self._types_holder)
        self.card_zones.v.addLayout(self._zones_holder)
        gr.addWidget(self.card_types, 3)
        gr.addWidget(self.card_zones, 2)
        root.addLayout(gr)

        # Dernières alertes
        recent = Card("Dernières alertes")
        top = QHBoxLayout()
        title = QLabel("Dernières alertes")
        title.setObjectName("sectionTitle")
        btn_map = QPushButton("🗺️ Voir la carte")
        btn_map.setObjectName("ghost")
        btn_map.clicked.connect(self.go_to_map.emit)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(btn_map)
        # remplace le titre par défaut de Card
        recent.v.takeAt(0).widget().deleteLater()
        recent.v.insertLayout(0, top)

        self.recent_table = _table(["Heure", "Type", "Quartier", "Distance", "Urgence", "Statut"])
        self.recent_table.setMinimumHeight(240)
        self.recent_table.cellDoubleClicked.connect(self._on_double)
        recent.add(self.recent_table)
        root.addWidget(recent)

        self._chart_types = None
        self._chart_zones = None

    def set_stats(self, stats):
        self.card_today.set_value(stats.get("today_count", 0))
        self.card_progress.set_value(stats.get("in_progress_count", 0))
        self.card_resolved.set_value(stats.get("resolved_count", 0))
        self.card_agents.set_value(stats.get("agents_connected", 0))

        # (Re)construit les graphiques
        _clear(self._types_holder)
        by_type = {k: v for k, v in (stats.get("by_type") or {}).items()}
        self._chart_types = charts.bar_chart(by_type, theme.ACCENT, height=220)
        self._types_holder.addWidget(self._chart_types)

        _clear(self._zones_holder)
        zones = {z["zone"]: z["count"] for z in (stats.get("by_commune") or [])[:6]}
        if zones:
            self._chart_zones = charts.donut_chart(zones, height=220)
        else:
            self._chart_zones = QLabel("Aucune donnée")
            self._chart_zones.setObjectName("muted")
        self._zones_holder.addWidget(self._chart_zones)

    def set_alerts(self, alerts):
        rows = alerts[:8]
        _fill_alert_table(self.recent_table, rows)

    def _on_double(self, row, _col):
        it = self.recent_table.item(row, 0)
        if it:
            self.request_focus.emit(int(it.data(Qt.UserRole)))


# --------------------------------------------------------------------------- #
# Alertes en direct
# --------------------------------------------------------------------------- #
class SearchBar(QFrame):
    """Barre de recherche avancée : texte, type, urgence, statut, dates."""

    search = Signal(dict)
    reset = Signal()

    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QComboBox, QDateEdit, QLineEdit
        from PySide6.QtCore import QDate

        self.setObjectName("card")
        lay = QGridLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setHorizontalSpacing(10)
        lay.setVerticalSpacing(8)

        self.q = QLineEdit()
        self.q.setPlaceholderText("🔎 Rechercher (citoyen, téléphone, quartier, description…)")
        self.q.returnPressed.connect(self._emit)
        lay.addWidget(self.q, 0, 0, 1, 4)

        self.f_type = QComboBox(); self.f_type.addItem("Tous types", "")
        for t in ["vol", "braquage", "incendie", "accident", "violence", "autre"]:
            self.f_type.addItem(t.capitalize(), t)
        self.f_urg = QComboBox(); self.f_urg.addItem("Toutes urgences", "")
        for u, lbl in [("faible", "Faible"), ("moyenne", "Moyen"), ("haute", "Élevé"), ("critique", "Critique")]:
            self.f_urg.addItem(lbl, u)
        self.f_status = QComboBox(); self.f_status.addItem("Tous statuts", "")
        for s, lbl in [("active", "En cours"), ("assignee", "Affectée"), ("cloturee", "Résolue")]:
            self.f_status.addItem(lbl, s)
        self.loc = QLineEdit(); self.loc.setPlaceholderText("📍 Localisation")

        self.d_from = QDateEdit(); self.d_from.setCalendarPopup(True)
        self.d_from.setDisplayFormat("dd/MM/yyyy"); self.d_from.setDate(QDate.currentDate().addMonths(-1))
        self.use_from = self._checkbox("Du")
        self.d_to = QDateEdit(); self.d_to.setCalendarPopup(True)
        self.d_to.setDisplayFormat("dd/MM/yyyy"); self.d_to.setDate(QDate.currentDate())
        self.use_to = self._checkbox("Au")

        lay.addWidget(self.f_type, 1, 0)
        lay.addWidget(self.f_urg, 1, 1)
        lay.addWidget(self.f_status, 1, 2)
        lay.addWidget(self.loc, 1, 3)

        drow = QHBoxLayout(); drow.setSpacing(8)
        drow.addWidget(self.use_from); drow.addWidget(self.d_from)
        drow.addWidget(self.use_to); drow.addWidget(self.d_to)
        drow.addStretch()
        btn = QPushButton("Rechercher"); btn.clicked.connect(self._emit)
        rst = QPushButton("Réinitialiser"); rst.setObjectName("ghost"); rst.clicked.connect(self._reset)
        drow.addWidget(rst); drow.addWidget(btn)
        lay.addLayout(drow, 2, 0, 1, 4)

    def _checkbox(self, text):
        from PySide6.QtWidgets import QCheckBox
        return QCheckBox(text)

    def _emit(self):
        f = {
            "q": self.q.text().strip(),
            "type": self.f_type.currentData(),
            "urgency": self.f_urg.currentData(),
            "status": self.f_status.currentData(),
            "neighborhood": self.loc.text().strip(),
        }
        if self.use_from.isChecked():
            f["date_from"] = self.d_from.date().toString("yyyy-MM-dd")
        if self.use_to.isChecked():
            f["date_to"] = self.d_to.date().toString("yyyy-MM-dd")
        self.search.emit({k: v for k, v in f.items() if v})

    def _reset(self):
        self.q.clear(); self.loc.clear()
        self.f_type.setCurrentIndex(0); self.f_urg.setCurrentIndex(0); self.f_status.setCurrentIndex(0)
        self.use_from.setChecked(False); self.use_to.setChecked(False)
        self.reset.emit()


class LiveAlertsPage(QWidget):
    request_assign = Signal(int)
    request_close = Signal(int)
    request_focus = Signal(int)
    open_incident = Signal(int)
    search = Signal(dict)
    reset_search = Signal()

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(14)

        self.search_bar = SearchBar()
        self.search_bar.search.connect(self.search.emit)
        self.search_bar.reset.connect(self.reset_search.emit)
        root.addWidget(self.search_bar)

        self.result_label = QLabel("")
        self.result_label.setObjectName("muted")
        root.addWidget(self.result_label)

        self.table = _table(
            ["Heure", "Type", "Citoyen", "Quartier", "Distance", "Urgence", "Statut"]
        )
        self.table.cellDoubleClicked.connect(self._on_double)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        b_view = QPushButton("👁️ Détails de l'incident")
        b_view.setObjectName("ghost")
        b_map = QPushButton("📍 Voir sur la carte")
        b_map.setObjectName("ghost")
        b_assign = QPushButton("🚔 Affecter une équipe")
        b_assign.setObjectName("warn")
        b_close = QPushButton("✅ Clôturer")
        b_close.setObjectName("success")
        for b in (b_view, b_map, b_assign, b_close):
            actions.addWidget(b)
        actions.addStretch()
        root.addLayout(actions)

        b_view.clicked.connect(lambda: self._emit(self.open_incident))
        b_map.clicked.connect(lambda: self._emit(self.request_focus))
        b_assign.clicked.connect(lambda: self._emit(self.request_assign))
        b_close.clicked.connect(lambda: self._emit(self.request_close))

    def set_alerts(self, alerts, searching=False):
        _fill_alert_table(self.table, alerts, with_citizen=True)
        if searching:
            self.result_label.setText(f"🔎 {len(alerts)} résultat(s) pour la recherche")
        else:
            self.result_label.setText("")

    def _selected_id(self):
        items = self.table.selectedItems()
        return int(items[0].data(Qt.UserRole)) if items else None

    def _emit(self, signal):
        aid = self._selected_id()
        if aid is not None:
            signal.emit(aid)

    def _on_double(self, row, _col):
        it = self.table.item(row, 0)
        if it:
            self.open_incident.emit(int(it.data(Qt.UserRole)))


# --------------------------------------------------------------------------- #
# Carte interactive
# --------------------------------------------------------------------------- #
class MapPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        self.ready = False
        if WEBENGINE_AVAILABLE:
            self.view = QWebEngineView()
            self.view.loadFinished.connect(self._on_loaded)
            self.view.load(QUrl.fromLocalFile(os.path.join(BASE_DIR, "map.html")))
            root.addWidget(self.view)
        else:
            self.view = None
            lbl = QLabel("Module carte (QtWebEngine) indisponible.")
            lbl.setObjectName("muted")
            lbl.setAlignment(Qt.AlignCenter)
            root.addWidget(lbl)
        self._pending = None

    def _on_loaded(self, ok):
        self.ready = ok
        if ok and self._pending is not None:
            self.set_alerts(self._pending)

    def _run(self, js):
        if self.view and self.ready:
            self.view.page().runJavaScript(js)

    def set_alerts(self, alerts):
        import json

        if not self.ready:
            self._pending = alerts
            return
        self._run(f"window.setAlerts({json.dumps(alerts)});")

    def set_patrols(self, teams):
        import json

        self._run(f"window.setPatrols({json.dumps(teams)});")

    def set_agents(self, agents):
        import json

        self._run(f"window.setAgents({json.dumps(agents)});")

    def add_alert(self, alert):
        import json

        self._run(f"window.addAlert({json.dumps(alert)});")

    def focus(self, alert_id):
        self._run(f"window.focusAlert({alert_id});")


# --------------------------------------------------------------------------- #
# Statistiques
# --------------------------------------------------------------------------- #
class StatisticsPage(QWidget):
    def __init__(self):
        super().__init__()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(18)

        kpis = QHBoxLayout()
        kpis.setSpacing(16)
        self.k_total = StatCard("📈", "Total signalements", theme.ACCENT)
        self.k_resolved = StatCard("✅", "Interventions clôturées", "#22c55e")
        self.k_response = StatCard("⏱️", "Temps de réponse moyen", "#f97316")
        self.k_today = StatCard("📅", "Résolues aujourd'hui", theme.ACCENT_2)
        for c in (self.k_total, self.k_resolved, self.k_response, self.k_today):
            kpis.addWidget(c)
        root.addLayout(kpis)

        self.card_types = Card("Types d'incidents les plus fréquents")
        self._types_holder = QVBoxLayout()
        self.card_types.v.addLayout(self._types_holder)
        root.addWidget(self.card_types)

        self.card_communes = Card("Incidents par commune")
        self._communes_holder = QVBoxLayout()
        self.card_communes.v.addLayout(self._communes_holder)
        root.addWidget(self.card_communes)

    def set_stats(self, stats):
        self.k_total.set_value(stats.get("total_count", 0))
        self.k_resolved.set_value(stats.get("resolved_count", 0))
        rt = stats.get("avg_response_min")
        self.k_response.set_value(f"{rt} min" if rt is not None else "—")
        self.k_today.set_value(stats.get("resolved_today", 0))

        _clear(self._types_holder)
        self._types_holder.addWidget(charts.bar_chart(stats.get("by_type") or {}, theme.ACCENT, 240))

        _clear(self._communes_holder)
        communes = {z["zone"]: z["count"] for z in (stats.get("by_commune") or [])}
        if communes:
            self._communes_holder.addWidget(charts.bar_chart(communes, theme.ACCENT_2, 240))
        else:
            lbl = QLabel("Aucune donnée")
            lbl.setObjectName("muted")
            self._communes_holder.addWidget(lbl)


# --------------------------------------------------------------------------- #
# Gestion des agents / citoyens / historique
# --------------------------------------------------------------------------- #
class PeoplePage(QWidget):
    """Page tabulaire générique (agents, citoyens)."""

    def __init__(self, headers, empty="Aucune donnée"):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        self.table = _table(headers)
        root.addWidget(self.table)
        self._empty = empty

    def set_rows(self, rows):
        self.table.setRowCount(len(rows))
        for i, cells in enumerate(rows):
            for j, (text, color) in enumerate(cells):
                self.table.setItem(i, j, _item(text, color))


class AgentsPage(QWidget):
    """Suivi opérationnel des agents en temps réel (superviseur)."""

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(14)

        cards = QHBoxLayout(); cards.setSpacing(16)
        self.c_total = StatCard("👮", "Agents", theme.ACCENT)
        self.c_avail = StatCard("🟢", "Disponibles", "#22c55e")
        self.c_busy = StatCard("🟠", "En intervention", "#f97316")
        self.c_offline = StatCard("⚫", "Hors service", theme.MUTED)
        for c in (self.c_total, self.c_avail, self.c_busy, self.c_offline):
            cards.addWidget(c)
        root.addLayout(cards)

        title = QLabel("Agents actifs — position, disponibilité, progression")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        self.table = _table(["Nom", "Rôle", "Disponibilité", "Position", "Intervention", "Vu à"])
        root.addWidget(self.table, 1)
        self.agents = {}

    def set_agents(self, agents):
        self.agents = {a["id"]: a for a in agents}
        self._render()

    def update_agent(self, agent):
        self.agents[agent["id"]] = agent
        self._render()

    def _render(self):
        agents = sorted(self.agents.values(), key=lambda a: (a.get("availability") != "busy", a["name"]))
        avail_colors = {"available": "#22c55e", "busy": "#f97316", "offline": theme.MUTED}
        avail_labels = {"available": "🟢 Disponible", "busy": "🟠 En intervention", "offline": "⚫ Hors service"}
        self.table.setRowCount(len(agents))
        n_av = n_bu = n_of = 0
        for i, a in enumerate(agents):
            av = a.get("availability", "offline")
            n_av += av == "available"; n_bu += av == "busy"; n_of += av == "offline"
            pos = f"{a['lat']:.4f}, {a['lng']:.4f}" if a.get("lat") is not None else "—"
            interv = f"#{a['current_alert_id']}" if a.get("current_alert_id") else "—"
            seen = (a.get("last_seen") or "—")[11:19] if a.get("last_seen") else "—"
            cells = [
                (a["name"], None), (a["role"].capitalize(), theme.ACCENT_2),
                (avail_labels.get(av, av), avail_colors.get(av)),
                (pos, None), (interv, "#f97316" if interv != "—" else theme.MUTED), (seen, theme.MUTED),
            ]
            for j, (text, color) in enumerate(cells):
                self.table.setItem(i, j, _item(text, color))
        self.c_total.set_value(len(agents))
        self.c_avail.set_value(n_av); self.c_busy.set_value(n_bu); self.c_offline.set_value(n_of)


class AnalyticsPage(QWidget):
    """Analyse de performance des agents (hebdo / mensuel / annuel)."""

    period_changed = Signal(str)

    def __init__(self):
        super().__init__()
        scroll = QScrollArea(self); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)
        content = QWidget(); scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 24); root.setSpacing(16)

        from PySide6.QtWidgets import QComboBox
        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(QLabel("Période :"))
        self.period = QComboBox()
        for lbl, val in [("Hebdomadaire", "week"), ("Mensuel", "month"), ("Annuel", "year")]:
            self.period.addItem(lbl, val)
        self.period.setCurrentIndex(1)
        self.period.currentIndexChanged.connect(lambda: self.period_changed.emit(self.period.currentData()))
        top.addWidget(self.period)
        root.addLayout(top)

        cards = QHBoxLayout(); cards.setSpacing(16)
        self.k_int = StatCard("🎯", "Interventions", theme.ACCENT)
        self.k_res = StatCard("✅", "Résolues", "#22c55e")
        self.k_rate = StatCard("📊", "Taux de résolution", "#a78bfa")
        self.k_resp = StatCard("⏱️", "Réponse moyenne", "#f97316")
        for c in (self.k_int, self.k_res, self.k_rate, self.k_resp):
            cards.addWidget(c)
        root.addLayout(cards)

        self.card_chart = Card("Interventions par agent")
        self._chart_holder = QVBoxLayout()
        self.card_chart.v.addLayout(self._chart_holder)
        root.addWidget(self.card_chart)

        title = QLabel("Détail par agent")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        self.table = _table(
            ["Agent", "Rôle", "Interventions", "Résolues", "Taux", "Réponse moy.", "Distance"]
        )
        root.addWidget(self.table)

    def set_data(self, data):
        self.k_int.set_value(data.get("total_interventions", 0))
        self.k_res.set_value(data.get("total_resolved", 0))
        self.k_rate.set_value(f"{data.get('global_resolution_rate', 0)}%")
        gr = data.get("global_avg_response_min")
        self.k_resp.set_value(f"{gr} min" if gr is not None else "—")

        rows = data.get("agents", [])
        _clear(self._chart_holder)
        chart_data = {r["name"].replace("Agent ", ""): r["interventions"] for r in rows if r["role"] == "agent"}
        if chart_data and sum(chart_data.values()) > 0:
            self._chart_holder.addWidget(charts.bar_chart(chart_data, theme.ACCENT, 220))
        else:
            lbl = QLabel("Pas encore de données d'intervention pour cette période.")
            lbl.setObjectName("muted")
            self._chart_holder.addWidget(lbl)

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            rt = r.get("avg_response_min")
            cells = [
                (r["name"], None), (r["role"].capitalize(), theme.ACCENT_2),
                (str(r["interventions"]), None), (str(r["resolved"]), "#22c55e"),
                (f"{r['resolution_rate']}%", "#a78bfa"),
                (f"{rt} min" if rt is not None else "—", "#f97316"),
                (f"{round(r['distance_m']/1000, 2)} km" if r.get("distance_m") else "0 km", theme.MUTED),
            ]
            for j, (text, color) in enumerate(cells):
                self.table.setItem(i, j, _item(text, color))


class HistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        title = QLabel("Historique des alertes clôturées")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        self.table = _table(["Heure", "Type", "Citoyen", "Quartier", "Urgence", "Statut"])
        root.addWidget(self.table)

    def set_alerts(self, alerts):
        closed = [a for a in alerts if a.get("status") == "cloturee"]
        _fill_alert_table(self.table, closed, with_citizen=True, hide_distance=True)


# --------------------------------------------------------------------------- #
# Rapports & paramètres (informatif)
# --------------------------------------------------------------------------- #
class ReportsPage(QWidget):
    """Synthèse + génération/téléchargement de rapports PDF."""

    generate_pdf = Signal(str)  # émet la période choisie

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)

        self.summary = Card("Rapport de synthèse")
        self.lines = QLabel("—")
        self.lines.setStyleSheet("font-size: 14px; line-height: 1.8;")
        self.summary.add(self.lines)
        root.addWidget(self.summary)

        gen = Card("Générer un rapport PDF")
        row = QHBoxLayout()
        row.setSpacing(10)
        from PySide6.QtWidgets import QComboBox

        self.period = QComboBox()
        for label, value in [("Aujourd'hui", "today"), ("Ce mois-ci", "month"),
                             ("Cette année", "year"), ("Tout", "all")]:
            self.period.addItem(label, value)
        self.period.setCurrentIndex(3)
        btn = QPushButton("📄 Générer le PDF")
        btn.clicked.connect(lambda: self.generate_pdf.emit(self.period.currentData()))
        row.addWidget(QLabel("Période :"))
        row.addWidget(self.period, 1)
        row.addWidget(btn)
        gen.v.addLayout(row)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        gen.add(self.status)
        root.addWidget(gen)
        root.addStretch()

    def set_stats(self, stats):
        rt = stats.get("avg_response_min")
        self.lines.setText(
            f"• Total des signalements : <b>{stats.get('total_count', 0)}</b><br>"
            f"• Alertes en cours : <b>{stats.get('in_progress_count', 0)}</b><br>"
            f"• Interventions clôturées : <b>{stats.get('resolved_count', 0)}</b><br>"
            f"• Temps de réponse moyen : <b>{rt if rt is not None else '—'} min</b><br>"
            f"• Agents connectés : <b>{stats.get('agents_connected', 0)}</b>"
        )

    def set_status(self, text, ok=True):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {'#22c55e' if ok else '#ff8181'};")


class SettingsPage(QWidget):
    def __init__(self, api_base, operator):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)
        card = Card("Paramètres")
        card.add(QLabel(f"<b>Opérateur :</b> {operator.get('name', '—')}  "
                        f"({operator.get('role', '—')})"))
        card.add(QLabel(f"<b>Serveur :</b> {api_base}"))
        perms = ", ".join(operator.get("permissions", [])) or "—"
        card.add(QLabel(f"<b>Permissions :</b> {perms}"))
        card.add(QLabel("<b>Thème :</b> Sombre — Centre de commandement"))
        root.addWidget(card)
        root.addStretch()


# --------------------------------------------------------------------------- #
# Helpers de remplissage
# --------------------------------------------------------------------------- #
def _fill_alert_table(table, alerts, with_citizen=False, hide_distance=False):
    table.setRowCount(len(alerts))
    for i, a in enumerate(alerts):
        col = 0

        def put(text, color=None):
            nonlocal col
            it = _item(text, color)
            it.setData(Qt.UserRole, a["id"])
            table.setItem(i, col, it)
            col += 1

        put(a.get("time", "—"))
        put((a.get("type") or "").capitalize())
        if with_citizen:
            put(a.get("reporter_name") or "Anonyme")
        put(a.get("neighborhood") or "—")
        if not hide_distance:
            put(f"{round(a['distance_m'])} m" if a.get("distance_m") is not None else "—")
        put(theme.urgency_label(a.get("urgency")), theme.urgency_color(a.get("urgency")))
        put(theme.STATUS_LABELS.get(a.get("status"), a.get("status")),
            theme.STATUS_COLORS.get(a.get("status")))


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
