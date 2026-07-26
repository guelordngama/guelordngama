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
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


def _fmt_duration(seconds):
    """Formate une durée en secondes → « m:ss » (ex. 12 → « 0:12 »)."""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    if s < 0:
        s = 0
    return f"{s // 60}:{s % 60:02d}"


def _pill_style(color):
    """Feuille de style pour une pastille de situation colorée."""
    return (
        f"background: {color}22; color: {color}; border: 1px solid {color}55;"
        "border-radius: 14px; padding: 6px 14px; font-weight: 600;"
    )


_JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
_MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]


def _msg_day(created_at):
    """Renvoie la date (``date``) d'un message à partir de son ``created_at``
    ISO, ou ``None`` si absent/illisible."""
    if not created_at:
        return None
    from datetime import datetime

    txt = str(created_at).replace("Z", "").split(".")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


def _day_label(day):
    """Libellé de séparateur façon WhatsApp : Aujourd'hui / Hier / jour de la
    semaine (moins de 7 j) / date complète (« 24 juillet 2026 »)."""
    from datetime import date, timedelta

    today = date.today()
    if day == today:
        return "Aujourd'hui"
    if day == today - timedelta(days=1):
        return "Hier"
    if today - timedelta(days=6) <= day < today:
        return _JOURS_FR[day.weekday()]
    return f"{day.day} {_MOIS_FR[day.month - 1]} {day.year}"


# --------------------------------------------------------------------------- #
# Tableau de bord
# --------------------------------------------------------------------------- #
class DashboardPage(QWidget):
    request_focus = Signal(int)   # centrer une alerte sur la carte (id)
    navigate = Signal(int)        # aller vers une section (index de menu)
    go_to_map = Signal()

    # Index de menu latéral (miroir de MainWindow.IDX_*)
    NAV_ALERTS = 1
    NAV_AGENTS = 3

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

        # En-tête d'accueil : salutation + date, et pastille de situation
        head = QHBoxLayout()
        head.setSpacing(12)
        htext = QVBoxLayout()
        htext.setSpacing(2)
        self.greeting = QLabel("Tableau de bord")
        self.greeting.setObjectName("pageTitle")
        self.subhead = QLabel("")
        self.subhead.setObjectName("muted")
        htext.addWidget(self.greeting)
        htext.addWidget(self.subhead)
        head.addLayout(htext)
        head.addStretch()
        self.situation = QLabel("")
        self.situation.setObjectName("pill")
        self.situation.setAlignment(Qt.AlignCenter)
        head.addWidget(self.situation, 0, Qt.AlignVCenter)
        root.addLayout(head)

        # Rangée de tuiles (cliquables → navigation)
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card_today = StatCard("🚨", "Alertes aujourd'hui", theme.ACCENT)
        self.card_progress = StatCard("⏳", "Alertes en cours", "#f97316")
        self.card_resolved = StatCard("✅", "Alertes résolues", "#22c55e")
        self.card_agents = StatCard("👮", "Agents connectés", theme.ACCENT_2)
        for c in (self.card_today, self.card_progress, self.card_resolved, self.card_agents):
            c.set_clickable(True)
            cards.addWidget(c)
        # Les alertes mènent à la vue « Alertes en direct », les agents à leur page.
        self.card_today.clicked.connect(lambda: self.navigate.emit(self.NAV_ALERTS))
        self.card_progress.clicked.connect(lambda: self.navigate.emit(self.NAV_ALERTS))
        self.card_resolved.clicked.connect(lambda: self.navigate.emit(self.NAV_ALERTS))
        self.card_agents.clicked.connect(lambda: self.navigate.emit(self.NAV_AGENTS))
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
        today = stats.get("today_count", 0)
        in_progress = stats.get("in_progress_count", 0)
        resolved = stats.get("resolved_count", 0)
        agents = stats.get("agents_connected", 0)

        self.card_today.set_value(today)
        self.card_progress.set_value(in_progress)
        self.card_resolved.set_value(resolved)
        self.card_agents.set_value(agents)

        # En-tête : salutation selon l'heure + date du jour
        self._update_header()

        # Pastille de situation opérationnelle
        if in_progress <= 0:
            self.situation.setText("🟢  Situation calme")
            self.situation.setStyleSheet(_pill_style("#22c55e"))
        elif in_progress <= 3:
            self.situation.setText(f"🟠  {in_progress} intervention(s) en cours")
            self.situation.setStyleSheet(_pill_style("#f97316"))
        else:
            self.situation.setText(f"🔴  {in_progress} alertes actives")
            self.situation.setStyleSheet(_pill_style("#ef4444"))

        # Sous-titres contextuels des tuiles
        total_done = resolved + in_progress
        rate = round(100 * resolved / total_done) if total_done else 0
        self.card_today.set_subtitle("Cliquer pour voir les alertes")
        self.card_progress.set_subtitle(
            "Aucune en attente" if in_progress == 0 else "À suivre en priorité")
        self.card_resolved.set_subtitle(f"{rate}% des cas traités")
        self.card_agents.set_subtitle(
            "Aucun agent en ligne" if agents == 0 else "Disponibles sur le terrain")

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

    def _update_header(self):
        from datetime import datetime

        now = datetime.now()
        h = now.hour
        if h < 12:
            salut = "Bonjour"
        elif h < 18:
            salut = "Bon après-midi"
        else:
            salut = "Bonsoir"
        self.greeting.setText(f"{salut}, centre de supervision")
        self.subhead.setText(now.strftime("%A %d %B %Y").capitalize())

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
    request_assign_agent = Signal(int)
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

        self._unread = set()  # ids des alertes non lues par l'opérateur

        actions = QHBoxLayout()
        actions.setSpacing(10)
        b_view = QPushButton("👁️ Détails de l'incident")
        b_view.setObjectName("ghost")
        b_map = QPushButton("📍 Voir sur la carte")
        b_map.setObjectName("ghost")
        b_assign = QPushButton("🚔 Affecter une équipe")
        b_assign.setObjectName("warn")
        b_agent = QPushButton("👮 Affecter un agent")
        b_agent.setObjectName("warn")
        b_close = QPushButton("✅ Clôturer")
        b_close.setObjectName("success")
        for b in (b_view, b_map, b_assign, b_agent, b_close):
            actions.addWidget(b)
        actions.addStretch()
        root.addLayout(actions)

        b_view.clicked.connect(lambda: self._emit(self.open_incident))
        b_map.clicked.connect(lambda: self._emit(self.request_focus))
        b_assign.clicked.connect(lambda: self._emit(self.request_assign))
        b_agent.clicked.connect(lambda: self._emit(self.request_assign_agent))
        b_close.clicked.connect(lambda: self._emit(self.request_close))

    def set_alerts(self, alerts, searching=False):
        _fill_alert_table(self.table, alerts, with_citizen=True, unread_ids=self._unread)
        if searching:
            self.result_label.setText(f"🔎 {len(alerts)} résultat(s) pour la recherche")
        elif not alerts:
            self.result_label.setText("🕊️  Aucune alerte en cours pour le moment.")
        else:
            self.result_label.setText("")

    # ---- Marquage « non lu » par alerte ----
    def mark_unread(self, alert_id):
        self._unread.add(alert_id)

    def mark_read(self, alert_id):
        self._unread.discard(alert_id)

    def unread_count(self):
        return len(self._unread)

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
    def __init__(self, api_base=None):
        super().__init__()
        # URL du serveur SafeCity : sert à faire passer les tuiles de carte par le
        # proxy /tiles/ du backend (contourne le blocage des CDN par le pare-feu).
        self.api_base = api_base
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
            lbl = QLabel(
                "🗺️ Module carte (Qt WebEngine) indisponible.\n\n"
                "Installez le composant complet de PySide6 :\n"
                "    pip install PySide6-Addons\n"
                "(ou : pip install PySide6)\n\n"
                "puis relancez l'application.")
            lbl.setObjectName("muted")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color:{theme.MUTED}; font-size:14px; line-height:1.6;")
            root.addWidget(lbl)
        self._pending = None
        self._pending_agents = None
        self._pending_patrols = None

    def _on_loaded(self, ok):
        self.ready = ok
        if not ok:
            return
        # Bascule le fond de carte vers le proxy de tuiles du serveur SafeCity.
        if self.api_base:
            import json

            self._run(f"window.setTileServer({json.dumps(self.api_base)});")
        if self._pending is not None:
            self.set_alerts(self._pending)
        if self._pending_patrols is not None:
            self.set_patrols(self._pending_patrols)
        if self._pending_agents is not None:
            self.set_agents(self._pending_agents)

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

        if not self.ready:
            self._pending_patrols = teams
            return
        self._run(f"window.setPatrols({json.dumps(teams)});")

    def set_agents(self, agents):
        import json

        if not self.ready:
            self._pending_agents = agents
            return
        self._run(f"window.setAgents({json.dumps(agents)});")

    def focus_agent(self, lat, lng):
        self._run(f"window.focusAgentAt({lat}, {lng});")

    def show_route(self, a_lat, a_lng, b_lat, b_lng):
        self._run(f"window.showRoute([{a_lat}, {a_lng}], [{b_lat}, {b_lng}]);")

    def clear_route(self):
        self._run("window.clearRoute();")

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

    def __init__(self, headers, empty="Aucun citoyen inscrit pour le moment.",
                 noun="citoyen"):
        super().__init__()
        self._noun = noun
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(10)

        # En-tête : compteur (ex. « 3 citoyens inscrits »).
        self.count_label = QLabel("")
        self.count_label.setObjectName("sectionTitle")
        root.addWidget(self.count_label)

        self.table = _table(headers)
        root.addWidget(self.table)

        # État vide explicite (sinon un tableau vide ressemble à un bug).
        self._empty = empty
        self.empty_label = QLabel(empty)
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            f"color:{theme.MUTED}; font-size:15px; padding:40px;")
        self.empty_label.hide()
        root.addWidget(self.empty_label, 1)

    def set_rows(self, rows):
        rows = list(rows)
        self.table.setRowCount(len(rows))
        for i, cells in enumerate(rows):
            for j, (text, color) in enumerate(cells):
                self.table.setItem(i, j, _item(text, color))
        # Bascule affichage tableau / message « vide » et met à jour le compteur.
        has_rows = len(rows) > 0
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)
        n = len(rows)
        suffix = "" if n == 1 else "s"
        self.count_label.setText(f"{n} {self._noun}{suffix} inscrit{suffix}")


class AgentsPage(QWidget):
    """Gestion + suivi opérationnel des agents en temps réel."""

    request_add = Signal()
    request_edit = Signal(dict)
    request_delete = Signal(dict)
    request_locate = Signal(dict)
    request_route = Signal(dict)
    request_history = Signal(dict)

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

        # Barre d'outils de gestion
        tools = QHBoxLayout()
        title = QLabel("Agents — gestion & suivi terrain")
        title.setObjectName("sectionTitle")
        tools.addWidget(title)
        tools.addStretch()
        b_add = QPushButton("➕ Ajouter"); b_add.setObjectName("success")
        b_edit = QPushButton("✏️ Modifier"); b_edit.setObjectName("ghost")
        b_del = QPushButton("🗑️ Supprimer"); b_del.setObjectName("danger")
        b_loc = QPushButton("📍 Localiser"); b_loc.setObjectName("ghost")
        b_route = QPushButton("🧭 Itinéraire"); b_route.setObjectName("ghost")
        b_hist = QPushButton("📜 Interventions"); b_hist.setObjectName("ghost")
        for b in (b_hist, b_route, b_loc, b_edit, b_del, b_add):
            tools.addWidget(b)
        root.addLayout(tools)

        b_add.clicked.connect(self.request_add.emit)
        b_edit.clicked.connect(lambda: self._with_selected(self.request_edit))
        b_del.clicked.connect(lambda: self._with_selected(self.request_delete))
        b_loc.clicked.connect(lambda: self._with_selected(self.request_locate))
        b_route.clicked.connect(lambda: self._with_selected(self.request_route))
        b_hist.clicked.connect(lambda: self._with_selected(self.request_history))

        self.table = _table(["Nom", "Rôle", "Disponibilité", "Téléphone", "Position", "Intervention", "Vu à"])
        self.table.cellDoubleClicked.connect(lambda *_: self._with_selected(self.request_edit))
        root.addWidget(self.table, 1)
        self.agents = {}
        self._unread = set()  # ids des agents modifiés non encore consultés

    def set_unread(self, ids):
        self._unread = set(ids)
        self._render()

    def _selected_agent(self):
        items = self.table.selectedItems()
        if not items:
            return None
        return self.agents.get(items[0].data(Qt.UserRole))

    def _with_selected(self, signal):
        a = self._selected_agent()
        if a:
            signal.emit(a)

    def set_agents(self, agents):
        self.agents = {a["id"]: a for a in agents}
        self._render()

    def update_agent(self, agent):
        self.agents[agent["id"]] = agent
        self._render()

    def remove_agent(self, agent_id):
        self.agents.pop(agent_id, None)
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
                (a.get("phone") or "—", None),
                (pos, None), (interv, "#f97316" if interv != "—" else theme.MUTED), (seen, theme.MUTED),
            ]
            is_unread = a["id"] in self._unread
            for j, (text, color) in enumerate(cells):
                item = _item(text, color, bold=is_unread)
                item.setData(Qt.UserRole, a["id"])
                if is_unread:
                    item.setBackground(QColor(theme.ACCENT + "22"))
                self.table.setItem(i, j, item)
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
    export_csv = Signal()
    export_xlsx = Signal()

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        top = QHBoxLayout()
        title = QLabel("Historique des alertes clôturées")
        title.setObjectName("sectionTitle")
        top.addWidget(title)
        top.addStretch()
        b_csv = QPushButton("⬇️ Exporter CSV"); b_csv.setObjectName("ghost")
        b_xlsx = QPushButton("⬇️ Exporter Excel"); b_xlsx.setObjectName("success")
        b_csv.clicked.connect(self.export_csv.emit)
        b_xlsx.clicked.connect(self.export_xlsx.emit)
        top.addWidget(b_csv); top.addWidget(b_xlsx)
        root.addLayout(top)
        self.table = _table(["Heure", "Type", "Citoyen", "Quartier", "Urgence", "Statut"])
        root.addWidget(self.table)

    def set_alerts(self, alerts):
        closed = [a for a in alerts if a.get("status") == "cloturee"]
        _fill_alert_table(self.table, closed, with_citizen=True, hide_distance=True)


class ChatPage(QWidget):
    """Messagerie temps réel entre opérateurs et agents (style WhatsApp).

    Bulles arrondies : mes messages (opérateur/administrateur) **à droite** (vert),
    ceux des agents **à gauche** (gris), ajustées au contenu, avec l'heure.
    """

    send = Signal(str, str, str, int, str)  # (texte, image, vocal, durée s, vidéo)
    request_participants = Signal()          # demande la liste « Infos »

    # Couleurs façon WhatsApp
    BUBBLE_ME = "#005c4b"       # vert (mes messages)
    BUBBLE_OTHER = "#202c33"    # gris (messages des agents)
    TEXT_COLOR = "#e9edef"
    TIME_COLOR = "#aebac1"

    def __init__(self, operator, api_base=""):
        super().__init__()
        from PySide6.QtWidgets import QLineEdit

        self.me_id = operator.get("id")
        self.api_base = api_base.rstrip("/")
        self._attachment = None
        self._video = None          # data URL de la vidéo prête à envoyer
        self._voice = None          # data URL du message vocal prêt à envoyer
        self._voice_dur = 0         # durée (s) du vocal prêt à envoyer
        self._recorder = None       # VoiceRecorder actif
        self._rec_timer = None      # minuteur d'affichage de la durée
        self._rec_start = 0.0       # instant de départ (monotone) de l'enregistrement
        self._player = None         # lecteur pour écouter les vocaux reçus
        self._read_frontier = ""    # accusés de lecture : horodatage « vu » le + récent
        self._sent_ticks = []       # (created_at, lbl_heure, texte_heure) de MES messages
        self._info_dialog = None    # fenêtre « Infos » (participants)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("💬 Messagerie opérateurs ↔ agents")
        title.setObjectName("sectionTitle")
        btn_info = QPushButton("ℹ️ Infos")
        btn_info.setObjectName("ghost")
        btn_info.setToolTip("Voir les participants : en ligne et qui a lu")
        btn_info.setCursor(Qt.PointingHandCursor)
        btn_info.clicked.connect(self.request_participants.emit)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(btn_info)
        root.addLayout(title_row)

        # Zone de messages défilante contenant les bulles.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("chatScroll")
        self._apply_scroll_style()
        self._host = QWidget()
        self._host.setStyleSheet("background: transparent;")
        self._msgs = QVBoxLayout(self._host)
        self._msgs.setContentsMargins(14, 14, 14, 14)
        self._msgs.setSpacing(8)
        self._msgs.addStretch()  # garde les bulles collées en haut
        self.scroll.setWidget(self._host)
        root.addWidget(self.scroll, 1)

        self.attach_label = QLabel("")
        self.attach_label.setObjectName("muted")
        root.addWidget(self.attach_label)

        row = QHBoxLayout()
        b_attach = QPushButton("📎")
        b_attach.setObjectName("ghost")
        b_attach.setFixedWidth(46)
        b_attach.setToolTip("Joindre une image")
        b_attach.clicked.connect(self._pick_attachment)

        b_video = QPushButton("🎥")
        b_video.setObjectName("ghost")
        b_video.setFixedWidth(46)
        b_video.setToolTip("Joindre une vidéo")
        b_video.clicked.connect(self._pick_video)

        self.btn_mic = QPushButton("🎤")
        self.btn_mic.setObjectName("ghost")
        self.btn_mic.setFixedWidth(46)
        self.btn_mic.setToolTip("Enregistrer un message vocal")
        self.btn_mic.clicked.connect(self._toggle_record)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Écrire un message aux agents…")
        self.input.returnPressed.connect(self._send)
        btn = QPushButton("Envoyer")
        btn.clicked.connect(self._send)
        row.addWidget(b_attach)
        row.addWidget(b_video)
        row.addWidget(self.btn_mic)
        row.addWidget(self.input, 1)
        row.addWidget(btn)
        root.addLayout(row)

        # Le bouton micro n'apparaît que si l'enregistrement est possible.
        try:
            import voice_recorder
            if not voice_recorder.available():
                self.btn_mic.hide()
        except Exception:
            self.btn_mic.hide()

    def _apply_scroll_style(self):
        self.scroll.setStyleSheet(
            f"QScrollArea#chatScroll {{ background: {theme.BG_ALT}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 14px; }}")

    def apply_theme(self):
        """Rafraîchit les zones à style inline lors d'un changement de thème."""
        self._apply_scroll_style()

    def _pick_attachment(self):
        import base64
        import os

        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Joindre une image", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if not path:
            return
        ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
        with open(path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        self._attachment = f"data:image/{ext};base64,{data}"
        self.attach_label.setText(f"📎 Pièce jointe : {os.path.basename(path)}  (sera envoyée)")

    def _pick_video(self):
        import base64
        import os

        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Joindre une vidéo", "", "Vidéos (*.mp4 *.webm *.mov *.m4v *.ogg)")
        if not path:
            return
        size = os.path.getsize(path)
        if size > 20 * 1024 * 1024:
            self.attach_label.setText("🎥 Vidéo trop volumineuse (max 20 Mo). Choisissez une courte séquence.")
            return
        ext = os.path.splitext(path)[1].lstrip(".").lower() or "mp4"
        mime = {"mov": "quicktime"}.get(ext, ext)
        with open(path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        self._video = f"data:video/{mime};base64,{data}"
        self.attach_label.setText(f"🎥 Vidéo : {os.path.basename(path)}  (sera envoyée)")

    # ---- Message vocal ----
    def _toggle_record(self):
        import time

        import voice_recorder

        if self._recorder is not None:  # enregistrement en cours → on arrête
            self._voice_dur = round(time.monotonic() - self._rec_start)
            self._recorder.stop()
            return
        try:
            self._recorder = voice_recorder.VoiceRecorder(self)
        except Exception as e:
            self.attach_label.setText(f"🎤 Micro indisponible : {e}")
            self._recorder = None
            return
        self._recorder.finished.connect(self._on_voice_ready)
        self._recorder.failed.connect(self._on_voice_failed)
        self._recorder.start()
        self._rec_start = time.monotonic()
        self.btn_mic.setText("⏹")
        self.btn_mic.setStyleSheet("color: #ef4444;")
        from PySide6.QtCore import QTimer
        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._tick_record)
        self._rec_timer.start(1000)
        self._tick_record()

    def _tick_record(self):
        import time

        s = round(time.monotonic() - self._rec_start)
        self.attach_label.setText(f"🔴 Enregistrement… {s // 60}:{s % 60:02d}  (🎤 pour arrêter)")
        if s >= 120 and self._recorder:   # limite de sécurité : 2 min
            self._voice_dur = s
            self._recorder.stop()

    def _reset_mic_button(self):
        if self._rec_timer:
            self._rec_timer.stop()
            self._rec_timer = None
        self.btn_mic.setText("🎤")
        self.btn_mic.setStyleSheet("")

    def _on_voice_ready(self, data_url):
        self._reset_mic_button()
        self._recorder = None
        self._voice = data_url
        d = self._voice_dur
        self.attach_label.setText(
            f"🎤 Message vocal prêt ({d // 60}:{d % 60:02d}) — cliquez sur « Envoyer ».")

    def _on_voice_failed(self, msg):
        self._reset_mic_button()
        self._recorder = None
        self._voice = None
        self._voice_dur = 0
        self.attach_label.setText(f"🎤 Échec de l'enregistrement : {msg}")

    def _send(self):
        text = self.input.text().strip()
        if text or self._attachment or self._voice or self._video:
            self.send.emit(text, self._attachment or "", self._voice or "",
                           self._voice_dur or 0, self._video or "")
            self.input.clear()
            self._attachment = None
            self._video = None
            self._voice = None
            self._voice_dur = 0
            self.attach_label.setText("")

    # ---- Rendu des messages ----
    def set_messages(self, msgs, unread_ids=None):
        unread_ids = unread_ids or set()
        self._clear_messages()
        self._last_day = None  # séparateur de date façon WhatsApp
        divider_done = False
        for m in msgs:
            self._maybe_add_date_divider(m)
            is_unread = m.get("id") in unread_ids
            if is_unread and not divider_done:
                self._add_divider("Nouveaux messages")
                divider_done = True
            self._add_bubble(m, unread=is_unread)
        self._scroll_to_bottom()

    def add_message(self, m):
        self._maybe_add_date_divider(m)
        self._add_bubble(m)
        self._scroll_to_bottom()

    def _maybe_add_date_divider(self, m):
        """Insère une pastille de date (Aujourd'hui / Hier / 24 juillet 2026)
        avant le premier message d'un nouveau jour, comme sur WhatsApp."""
        day = _msg_day(m.get("created_at"))
        if day is None:
            return
        if day != getattr(self, "_last_day", None):
            self._add_date_divider(_day_label(day))
            self._last_day = day

    def _clear_messages(self):
        self._sent_ticks = []
        # Retire toutes les bulles en gardant le stretch final.
        while self._msgs.count() > 1:
            item = self._msgs.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ---- Accusés de lecture ----
    @staticmethod
    def _tick_html(read):
        if read:
            return "<span style='color:#53bdeb;'>✓✓</span>"
        return "<span style='color:#8696a0;'>✓</span>"

    # ---- Onglet « Infos » (participants) ----
    def show_participants(self, data):
        from PySide6.QtWidgets import (QDialog, QLabel, QListWidget, QPushButton,
                                       QVBoxLayout)

        if self._info_dialog is None:
            dlg = QDialog(self)
            dlg.setWindowTitle("Infos — participants")
            dlg.resize(380, 480)
            lay = QVBoxLayout(dlg)
            legend = QLabel("🟢 en ligne · ⚪ hors ligne · ✓✓ a vu le dernier message")
            legend.setObjectName("muted")
            legend.setWordWrap(True)
            lay.addWidget(legend)
            self._info_list = QListWidget()
            self._info_list.setStyleSheet(
                f"QListWidget {{ background: {theme.BG_ALT}; color: {theme.TEXT};"
                f"border: 1px solid {theme.BORDER}; border-radius: 10px; padding: 4px; }}"
                "QListWidget::item { padding: 6px 4px; }")
            lay.addWidget(self._info_list, 1)
            b = QPushButton("🔄 Actualiser")
            b.clicked.connect(self.request_participants.emit)
            lay.addWidget(b)
            dlg.finished.connect(lambda _=0: setattr(self, "_info_dialog", None))
            self._info_dialog = dlg
            self._populate_info(data)
            dlg.show()
        else:
            self._populate_info(data)

    def info_open(self):
        return self._info_dialog is not None

    def _populate_info(self, data):
        self._info_list.clear()
        for u in data or []:
            dot = "🟢" if u.get("online") else "⚪"
            seen = "✓✓ a vu" if u.get("read_latest") else "…  pas encore vu"
            role = (u.get("role") or "").capitalize()
            self._info_list.addItem(f"{dot}  {u.get('name')}  ({role})\n        {seen}")

    def apply_read(self, data):
        """Met à jour les ✓✓ quand un autre participant a lu la messagerie."""
        if not isinstance(data, dict):
            return
        if data.get("reader_id") == self.me_id:
            return
        seen = data.get("seen_at") or ""
        if seen and seen > self._read_frontier:
            self._read_frontier = seen
        for created, lbl, base in self._sent_ticks:
            read = created and created <= self._read_frontier
            try:
                lbl.setText(base + "  " + self._tick_html(read))
            except RuntimeError:
                pass  # widget supprimé

    def _add_divider(self, label):
        lbl = QLabel(f"──  {label}  ──")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {theme.ACCENT_2}; font-size: 11px; font-weight: bold; background: transparent;")
        self._msgs.insertWidget(self._msgs.count() - 1, lbl)

    def _add_date_divider(self, label):
        """Pastille de date centrée (style WhatsApp) séparant les jours."""
        chip = QLabel(label)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            "QLabel { background: rgba(0,0,0,0.35); color: #e9edef; font-size: 11px;"
            "font-weight: 600; border-radius: 10px; padding: 4px 12px; }")
        line = QHBoxLayout()
        line.setContentsMargins(0, 4, 0, 4)
        line.addStretch()
        line.addWidget(chip)
        line.addStretch()
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        wrap.setLayout(line)
        self._msgs.insertWidget(self._msgs.count() - 1, wrap)

    def _add_bubble(self, m, unread=False):
        mine = m.get("sender_id") == self.me_id
        bg = self.BUBBLE_ME if mine else self.BUBBLE_OTHER
        name_color = "#8fe3cf" if mine else theme.ACCENT_2

        bubble = QFrame()
        bubble.setObjectName("bubble")
        border = f"border: 2px solid {theme.ACCENT_2};" if unread else "border: none;"
        bubble.setStyleSheet(
            f"QFrame#bubble {{ background: {bg}; border-radius: 12px; {border} }}")
        bubble.setMaximumWidth(440)
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(12, 7, 12, 6)
        bl.setSpacing(2)

        role = (m.get("sender_role") or "").capitalize()
        name = "Moi" if mine else f"{m.get('sender_name') or 'Agent'} · {role}"
        if unread and not mine:
            name = "🔵 " + name
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet(
            f"color: {name_color}; font-size: 11px; font-weight: bold; background: transparent;")
        bl.addWidget(lbl_name)

        if m.get("text"):
            lbl_text = QLabel(m["text"])
            lbl_text.setWordWrap(True)
            lbl_text.setStyleSheet(f"color: {self.TEXT_COLOR}; font-size: 13px; background: transparent;")
            bl.addWidget(lbl_text)

        if m.get("voice_url"):
            bl.addWidget(self._voice_player(self.api_base + m["voice_url"],
                                            m.get("voice_duration")))

        if m.get("attachment_url"):
            bl.addWidget(self._photo_view(self.api_base + m["attachment_url"]))

        if m.get("video_url"):
            bl.addWidget(self._video_view(self.api_base + m["video_url"]))

        lbl_time = QLabel(m.get("time", ""))
        lbl_time.setAlignment(Qt.AlignRight)
        lbl_time.setTextFormat(Qt.RichText)
        lbl_time.setStyleSheet(f"color: {self.TIME_COLOR}; font-size: 10px; background: transparent;")
        bl.addWidget(lbl_time)

        # Accusé de lecture (✓ / ✓✓) sur MES messages.
        if mine:
            base = m.get("time", "")
            created = m.get("created_at") or ""
            read = bool(m.get("read")) or (created and created <= self._read_frontier)
            lbl_time.setText(base + "  " + self._tick_html(read))
            self._sent_ticks.append((created, lbl_time, base))

        # Ligne : bulle poussée à droite (moi) ou à gauche (agent).
        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        if mine:
            line.addStretch()
            line.addWidget(bubble)
        else:
            line.addWidget(bubble)
            line.addStretch()
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        wrap.setLayout(line)
        self._msgs.insertWidget(self._msgs.count() - 1, wrap)

    def _voice_player(self, url, duration=None):
        """Petit lecteur « ▶ Message vocal · m:ss » pour écouter un vocal reçu."""
        btn = QPushButton()
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.12); color: #e9edef;"
            "border: none; border-radius: 8px; padding: 6px 12px; text-align: left; }"
            "QPushButton:hover { background: rgba(255,255,255,0.2); }")
        btn._idle_label = "▶  Message vocal" + (f"  ·  {_fmt_duration(duration)}" if duration else "")
        btn.setText(btn._idle_label)
        btn.clicked.connect(lambda: self._play_voice(url, btn))
        return btn

    def _play_voice(self, url, btn):
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception:
            self.attach_label.setText("🔊 Lecture audio non disponible sur ce poste.")
            return

        if self._player is None:
            self._audio_out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_out)
            self._player.playbackStateChanged.connect(self._on_play_state)
            self._player.errorOccurred.connect(self._on_play_error)

        from PySide6.QtMultimedia import QMediaPlayer as _QMP
        active = self._player.playbackState() != _QMP.PlaybackState.StoppedState

        # Clic sur le vocal déjà en cours → on l'ARRÊTE (ferme proprement).
        if getattr(self, "_playing_btn", None) is btn and active:
            self._player.stop()
            self._reset_play_btn()
            return

        # Sinon : couper l'éventuelle lecture en cours, puis lire celui-ci.
        if getattr(self, "_playing_btn", None) is not None:
            self._player.stop()
            self._reset_play_btn()
        self._playing_btn = btn
        self._audio_out.setVolume(1.0)
        self._player.setSource(QUrl(url))
        self._player.play()
        btn.setText("⏹  Arrêter")

    def _reset_play_btn(self):
        btn = getattr(self, "_playing_btn", None)
        if btn is not None:
            btn.setText(getattr(btn, "_idle_label", "▶  Message vocal"))
        self._playing_btn = None

    def _on_play_state(self, state):
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._reset_play_btn()

    def _on_play_error(self, *_a):
        self.attach_label.setText("🔊 Impossible de lire ce vocal (réseau ou format).")
        self._reset_play_btn()

    # ---- Pièces jointes image ----
    def _nam_get(self, url):
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

        if not hasattr(self, "_nam") or self._nam is None:
            self._nam = QNetworkAccessManager(self)
        return self._nam.get(QNetworkRequest(QUrl(url)))

    def _photo_view(self, url):
        """Miniature cliquable d'une image (clic = agrandissement)."""
        btn = QPushButton("🖼️  Chargement de l'image…")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.10); color: #e9edef;"
            "border: none; border-radius: 8px; padding: 6px 12px; text-align: left; }"
            "QPushButton:hover { background: rgba(255,255,255,0.18); }")
        btn.clicked.connect(lambda: self._open_image(url, getattr(btn, "_full_pixmap", None)))
        try:
            from PySide6.QtCore import QSize
            from PySide6.QtGui import QIcon, QPixmap

            reply = self._nam_get(url)

            def done():
                pix = QPixmap()
                if pix.loadFromData(reply.readAll()):
                    btn._full_pixmap = pix
                    thumb = pix.scaled(QSize(240, 170), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    btn.setText("")
                    btn.setIcon(QIcon(thumb))
                    btn.setIconSize(thumb.size())
                    btn.setToolTip("Cliquer pour agrandir")
                else:
                    btn.setText("📎  Pièce jointe (cliquer pour ouvrir)")
                reply.deleteLater()

            reply.finished.connect(done)
        except Exception:
            btn.setText("📎  Pièce jointe (cliquer pour ouvrir)")
        return btn

    def _open_image(self, url, pixmap=None):
        """Affiche l'image en grand dans une fenêtre."""
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("Pièce jointe")
        dlg.resize(760, 560)
        lay = QVBoxLayout(dlg)
        lbl = QLabel("Chargement…")
        lbl.setAlignment(Qt.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(lbl)
        lay.addWidget(scroll)

        def show(pix):
            if pix and not pix.isNull():
                lbl.setPixmap(pix.scaled(1400, 1000, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                lbl.setText("Impossible de charger l'image.")

        if pixmap is not None and not pixmap.isNull():
            show(pixmap)
        else:
            reply = self._nam_get(url)

            def done():
                p = QPixmap()
                p.loadFromData(reply.readAll())
                show(p)
                reply.deleteLater()

            reply.finished.connect(done)
        dlg.exec()

    # ---- Pièces jointes vidéo ----
    def _video_view(self, url):
        btn = QPushButton("🎥  Vidéo — cliquer pour lire")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.12); color: #e9edef;"
            "border: none; border-radius: 8px; padding: 6px 12px; text-align: left; }"
            "QPushButton:hover { background: rgba(255,255,255,0.2); }")
        btn.clicked.connect(lambda: self._open_video(url))
        return btn

    def _open_video(self, url):
        """Lit la vidéo dans une fenêtre (QVideoWidget) ; repli sur le lecteur système."""
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget
            from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout
        except Exception:
            self._open_video_external(url)
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Vidéo")
        dlg.resize(760, 520)
        lay = QVBoxLayout(dlg)
        video_w = QVideoWidget()
        lay.addWidget(video_w, 1)
        bar = QHBoxLayout()
        b_play = QPushButton("⏸  Pause")
        b_ext = QPushButton("Ouvrir dans le lecteur système")
        b_ext.setObjectName("ghost")
        bar.addWidget(b_play)
        bar.addStretch()
        bar.addWidget(b_ext)
        lay.addLayout(bar)

        player = QMediaPlayer(dlg)
        audio = QAudioOutput(dlg)
        player.setAudioOutput(audio)
        player.setVideoOutput(video_w)
        player.setSource(QUrl(url))
        player.play()

        def toggle():
            if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.pause(); b_play.setText("▶  Lire")
            else:
                player.play(); b_play.setText("⏸  Pause")

        b_play.clicked.connect(toggle)
        b_ext.clicked.connect(lambda: self._open_video_external(url))
        dlg.finished.connect(lambda _=0: player.stop())
        dlg.exec()

    def _open_video_external(self, url):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl(url))

    def _scroll_to_bottom(self):
        from PySide6.QtCore import QTimer
        bar = self.scroll.verticalScrollBar()
        QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))


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
    change_password = Signal(str, str)  # (mot de passe actuel, nouveau)
    server_changed = Signal(str)        # nouvelle adresse de serveur enregistrée

    def __init__(self, api_base, operator):
        super().__init__()
        from PySide6.QtWidgets import QFormLayout, QLineEdit

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)
        card = Card("Paramètres")
        card.add(QLabel(f"<b>Opérateur :</b> {operator.get('name', '—')}  "
                        f"({operator.get('role', '—')})"))
        perms = ", ".join(operator.get("permissions", [])) or "—"
        card.add(QLabel(f"<b>Permissions :</b> {perms}"))
        card.add(QLabel("<b>Thème :</b> Sombre — Centre de commandement"))
        root.addWidget(card)

        # --- Serveur (modifiable) ---
        srv_card = Card("🌐 Serveur")
        srv_card.add(QLabel("Adresse du serveur SafeCity (API + temps réel) :"))
        self.server_input = QLineEdit(api_base)
        self.server_input.setPlaceholderText("https://safecity-lubumbashi.com")
        srv_card.add(self.server_input)
        self.server_info = QLabel(
            "Serveur de production : safecity-lubumbashi.com (169.58.47.76).")
        self.server_info.setObjectName("muted"); self.server_info.setWordWrap(True)
        srv_card.add(self.server_info)
        btn_srv = QPushButton("Enregistrer le serveur"); btn_srv.setObjectName("success")
        btn_srv.clicked.connect(self._save_server)
        srv_card.add(btn_srv)
        root.addWidget(srv_card)

        # --- Changer mon mot de passe ---
        pw_card = Card("🔒 Changer mon mot de passe")
        form = QFormLayout()
        form.setSpacing(10)
        self.pw_current = QLineEdit(); self.pw_current.setEchoMode(QLineEdit.Password)
        self.pw_current.setPlaceholderText("Mot de passe actuel")
        self.pw_new = QLineEdit(); self.pw_new.setEchoMode(QLineEdit.Password)
        self.pw_new.setPlaceholderText("Nouveau (min. 6 caractères)")
        self.pw_new2 = QLineEdit(); self.pw_new2.setEchoMode(QLineEdit.Password)
        self.pw_new2.setPlaceholderText("Confirmer le nouveau")
        form.addRow("Actuel", self.pw_current)
        form.addRow("Nouveau", self.pw_new)
        form.addRow("Confirmer", self.pw_new2)
        pw_card.add_layout(form)
        self.pw_info = QLabel(""); self.pw_info.setObjectName("muted"); self.pw_info.setWordWrap(True)
        pw_card.add(self.pw_info)
        btn = QPushButton("Modifier le mot de passe"); btn.setObjectName("success")
        btn.clicked.connect(self._submit_password)
        pw_card.add(btn)
        root.addWidget(pw_card)
        root.addStretch()

    def _save_server(self):
        url = self.server_input.text().strip().rstrip("/")
        if not (url.startswith("http://") or url.startswith("https://")):
            self.server_info.setText("⚠ L'adresse doit commencer par http:// ou https://")
            self.server_info.setStyleSheet("color: #ff8181;")
            return
        self.server_changed.emit(url)
        self.server_info.setText(
            "✅ Serveur enregistré. Redémarrez l'application pour vous y connecter.")
        self.server_info.setStyleSheet("color: #22c55e;")

    def _submit_password(self):
        cur, new, new2 = self.pw_current.text(), self.pw_new.text(), self.pw_new2.text()
        if not cur or not new:
            self._pw_msg("Renseignez le mot de passe actuel et le nouveau.", err=True); return
        if len(new) < 6:
            self._pw_msg("Le nouveau mot de passe doit contenir au moins 6 caractères.", err=True); return
        if new != new2:
            self._pw_msg("Les deux nouveaux mots de passe ne correspondent pas.", err=True); return
        self.change_password.emit(cur, new)

    def _pw_msg(self, text, err=False):
        self.pw_info.setText(text)
        self.pw_info.setStyleSheet("color: #ff8181;" if err else "color: #22c55e;")

    def password_changed_ok(self):
        self.pw_current.clear(); self.pw_new.clear(); self.pw_new2.clear()
        self._pw_msg("✅ Mot de passe modifié avec succès.")

    def password_change_failed(self, message):
        self._pw_msg("Échec : " + message, err=True)


class AboutPage(QWidget):
    """Onglet « À propos » : présentation de la plateforme et du créateur."""

    APP_VERSION = "1.0.0"
    APP_YEAR = "2026"

    def __init__(self):
        super().__init__()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)

        # En-tête
        header = QHBoxLayout()
        logo = QLabel("🛡️")
        logo.setStyleSheet("font-size: 48px;")
        htxt = QVBoxLayout()
        htxt.setSpacing(2)
        t = QLabel("SafeCity Lubumbashi")
        t.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {theme.ACCENT};")
        st = QLabel("Solution numérique de sécurité citoyenne")
        st.setObjectName("muted")
        htxt.addWidget(t)
        htxt.addWidget(st)
        header.addWidget(logo)
        header.addSpacing(12)
        header.addLayout(htxt)
        header.addStretch()
        root.addLayout(header)

        # Présentation
        pres = Card("À propos de la plateforme")
        intro = QLabel(
            "SafeCity Lubumbashi est une solution numérique de sécurité citoyenne "
            "conçue par <b>Guelord Ngama Wa Ngama</b>, licencié en Informatique de Gestion.<br><br>"
            "Passionné par les nouvelles technologies et l'innovation, j'ai développé "
            "cette plateforme afin de contribuer à l'amélioration de la sécurité dans nos "
            "communautés grâce à la technologie.<br><br>"
            "L'application permet aux citoyens de signaler rapidement des situations "
            "dangereuses, de partager leur localisation en cas d'urgence et de faciliter "
            "l'intervention des agents de sécurité."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 14px; line-height: 1.7;")
        pres.add(intro)
        root.addWidget(pres)

        # Créateur
        creator = Card("Créateur")
        name = QLabel("Guelord Ngama Wa Ngama")
        name.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {theme.ACCENT};")
        role = QLabel("Développeur informatique | Ingénieur logiciel en formation continue")
        role.setObjectName("muted")
        role.setWordWrap(True)
        creator.add(name)
        creator.add(role)
        spec_title = QLabel("Spécialisé en :")
        spec_title.setStyleSheet("font-weight: 700; margin-top: 8px;")
        creator.add(spec_title)
        for item in [
            "Développement d'applications web et desktop",
            "Développement mobile Android",
            "Sécurité informatique",
            "Intelligence artificielle appliquée",
        ]:
            row = QLabel(f"  •  {item}")
            row.setStyleSheet("font-size: 14px;")
            creator.add(row)
        root.addWidget(creator)

        # Version
        version = Card("Informations")
        version.add(QLabel(f"<b>Version :</b> {self.APP_VERSION}"))
        version.add(QLabel(f"<b>Année :</b> {self.APP_YEAR}"))
        version.add(QLabel("<b>Ville :</b> Lubumbashi, RD Congo"))
        root.addWidget(version)

        credit = QLabel(f"© {self.APP_YEAR} SafeCity Lubumbashi — Guelord Ngama Wa Ngama. "
                        "Tous droits réservés.")
        credit.setObjectName("muted")
        credit.setAlignment(Qt.AlignCenter)
        root.addWidget(credit)
        root.addStretch()


# --------------------------------------------------------------------------- #
# Helpers de remplissage
# --------------------------------------------------------------------------- #
def _fill_alert_table(table, alerts, with_citizen=False, hide_distance=False, unread_ids=None):
    unread_ids = unread_ids or set()
    table.setRowCount(len(alerts))
    for i, a in enumerate(alerts):
        col = 0
        is_unread = a["id"] in unread_ids

        def put(text, color=None):
            nonlocal col
            it = _item(text, color, bold=is_unread)
            it.setData(Qt.UserRole, a["id"])
            if is_unread:
                it.setBackground(QColor(theme.ACCENT + "22"))  # fond teinté « non lu »
            table.setItem(i, col, it)
            col += 1

        time_txt = a.get("time", "—")
        put(("● " + time_txt) if is_unread else time_txt)
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
