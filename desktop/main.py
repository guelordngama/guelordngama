"""SafeCity — Application bureau du centre de surveillance (Mairie).

Interface PySide6 :
  - Tableau de bord (alertes du jour, actives, zones dangereuses, dernière alerte)
  - Alertes en direct (tableau : heure, type, quartier, distance)
  - Carte interactive OpenStreetMap (Qt WebEngine + Leaflet)
  - Graphiques (Qt Charts : répartition par type)
  - Actions : voir sur la carte, affecter une équipe, clôturer

Lancement :
    python -m desktop.main            (depuis la racine du dépôt)
    python desktop/main.py
"""
import json
import os
import sys

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Import robuste : on ajoute le dossier courant au chemin de recherche puis on
# utilise un import ABSOLU. Fonctionne aussi bien lancé comme script (bouton Run
# de PyCharm) que comme module (`python -m desktop.main`), sans import relatif.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_client import ApiClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_BASE = os.environ.get("SAFECITY_API", "http://localhost:5000")

URGENCY_COLORS = {
    "critique": "#9d0208",
    "haute": "#e76f51",
    "moyenne": "#e9a100",
    "faible": "#2a9d8f",
}


# --------------------------------------------------------------------------- #
# Pont Socket.IO -> Qt : reçoit les événements réseau et émet des signaux Qt.
# --------------------------------------------------------------------------- #
class RealtimeBridge(QThread):
    new_alert = Signal(dict)
    alert_updated = Signal(dict)
    connection_changed = Signal(bool)

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api

    def run(self):
        self.api.on("new_alert", lambda data: self.new_alert.emit(data))
        self.api.on("alert_updated", lambda data: self.alert_updated.emit(data))
        self.api.on("connect", lambda: self.connection_changed.emit(True))
        self.api.on("disconnect", lambda: self.connection_changed.emit(False))
        self.api.connect_realtime()


# --------------------------------------------------------------------------- #
# Carte de statistique (tuile du tableau de bord)
# --------------------------------------------------------------------------- #
class StatCard(QFrame):
    def __init__(self, title, color="#c1121f"):
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet(
            f"#statCard {{ background:#fff; border-radius:14px; border-left:5px solid {color}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self.value = QLabel("0")
        self.value.setStyleSheet(f"color:{color};")
        self.value.setFont(QFont("Segoe UI", 30, QFont.Bold))
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color:#6b6b7b;")
        title_lbl.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.value)
        layout.addWidget(title_lbl)

    def set_value(self, v):
        self.value.setText(str(v))


# --------------------------------------------------------------------------- #
# Dialogue de connexion opérateur
# --------------------------------------------------------------------------- #
class LoginDialog(QDialog):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.user = None
        self.setWindowTitle("Connexion — Centre SafeCity")
        self.setMinimumWidth(340)
        form = QFormLayout(self)
        self.email = QLineEdit("operateur@safecity.local")
        self.password = QLineEdit("safecity123")
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("Email", self.email)
        form.addRow("Mot de passe", self.password)
        btn = QPushButton("Se connecter")
        btn.clicked.connect(self._try_login)
        form.addRow(btn)
        self.info = QLabel("Compte de démonstration pré-rempli.")
        self.info.setStyleSheet("color:#6b6b7b; font-size:11px;")
        form.addRow(self.info)

    def _try_login(self):
        try:
            self.user = self.api.login(self.email.text().strip(), self.password.text())
            self.accept()
        except Exception as e:
            self.info.setText("Échec : " + str(e))
            self.info.setStyleSheet("color:#c1121f; font-size:11px;")


# --------------------------------------------------------------------------- #
# Fenêtre principale
# --------------------------------------------------------------------------- #
class MainWindow(QWidget):
    def __init__(self, api: ApiClient, operator):
        super().__init__()
        self.api = api
        self.operator = operator
        self.alerts = {}  # id -> dict
        self.teams = []

        self.setWindowTitle("SafeCity — Centre de surveillance (Mairie)")
        self.resize(1280, 820)
        self.setStyleSheet("QWidget { background:#f7f7fa; font-family:'Segoe UI'; }")

        self._build_ui()
        self._load_initial_data()
        self._start_realtime()

    # ---- Construction de l'interface ----
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # En-tête
        header = QHBoxLayout()
        title = QLabel("🛡️  SafeCity — Centre de surveillance")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color:#c1121f;")
        self.conn_lbl = QLabel("● Hors ligne")
        self.conn_lbl.setStyleSheet("color:#c1121f;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel(f"Opérateur : {self.operator.get('name', '—')}"))
        header.addWidget(self.conn_lbl)
        root.addLayout(header)

        # Tuiles de statistiques
        cards = QHBoxLayout()
        self.card_today = StatCard("Alertes du jour", "#c1121f")
        self.card_active = StatCard("Alertes actives", "#e76f51")
        self.card_zones = StatCard("Zones dangereuses", "#e9a100")
        self.card_last = StatCard("Total signalements", "#2a9d8f")
        for c in (self.card_today, self.card_active, self.card_zones, self.card_last):
            cards.addWidget(c)
        root.addLayout(cards)

        # Zone centrale : (gauche) tableau alertes + graphique, (droite) carte
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl_live = QLabel("🔴 Alertes en direct")
        lbl_live.setFont(QFont("Segoe UI", 13, QFont.Bold))
        left_layout.addWidget(lbl_live)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Heure", "Type", "Quartier", "Distance", "Urgence", "Statut"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.setStyleSheet("QTableWidget { background:#fff; border-radius:10px; }")
        left_layout.addWidget(self.table, 3)

        # Boutons d'action
        actions = QHBoxLayout()
        self.btn_map = QPushButton("📍 Voir sur la carte")
        self.btn_assign = QPushButton("🚔 Affecter une équipe")
        self.btn_close = QPushButton("✅ Clôturer")
        for b, color in (
            (self.btn_map, "#457b9d"),
            (self.btn_assign, "#e9a100"),
            (self.btn_close, "#2a9d8f"),
        ):
            b.setStyleSheet(
                f"QPushButton {{ background:{color}; color:#fff; padding:10px; "
                f"border:none; border-radius:8px; font-weight:bold; }}"
                f"QPushButton:hover {{ opacity:0.9; }}"
            )
            actions.addWidget(b)
        self.btn_map.clicked.connect(self._focus_selected_on_map)
        self.btn_assign.clicked.connect(self._assign_selected)
        self.btn_close.clicked.connect(self._close_selected)
        left_layout.addLayout(actions)

        # Graphique Qt Charts
        self.chart_view = self._build_chart()
        left_layout.addWidget(self.chart_view, 2)

        splitter.addWidget(left)

        # Carte (Qt WebEngine)
        self.map_view = QWebEngineView()
        self.map_view.load(QUrl.fromLocalFile(os.path.join(BASE_DIR, "map.html")))
        self.map_ready = False
        self.map_view.loadFinished.connect(self._on_map_loaded)
        splitter.addWidget(self.map_view)
        splitter.setSizes([560, 700])

        root.addWidget(splitter, 1)

    def _build_chart(self):
        self.bar_set = QBarSet("Alertes")
        self.chart = QChart()
        self.chart.setTitle("Répartition des incidents par type")
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        series = QBarSeries()
        series.append(self.bar_set)
        self.chart.addSeries(series)
        self.bar_series = series

        self.axis_x = QBarCategoryAxis()
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        series.attachAxis(self.axis_x)
        self.axis_y = QValueAxis()
        self.axis_y.setLabelFormat("%d")
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        series.attachAxis(self.axis_y)

        view = QChartView(self.chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setStyleSheet("background:#fff; border-radius:10px;")
        view.setMinimumHeight(220)
        return view

    # ---- Chargement initial ----
    def _load_initial_data(self):
        try:
            self.teams = self.api.get_teams()
            for a in self.api.get_alerts():
                self.alerts[a["id"]] = a
            self._refresh_table()
            self._refresh_stats()
        except Exception as e:
            QMessageBox.warning(self, "Erreur réseau",
                              f"Impossible de charger les données :\n{e}")

    # ---- Temps réel ----
    def _start_realtime(self):
        self.bridge = RealtimeBridge(self.api)
        self.bridge.new_alert.connect(self._on_new_alert)
        self.bridge.alert_updated.connect(self._on_alert_updated)
        self.bridge.connection_changed.connect(self._on_conn_changed)
        self.bridge.start()

    def _on_conn_changed(self, ok):
        self.conn_lbl.setText("● En ligne" if ok else "● Hors ligne")
        self.conn_lbl.setStyleSheet(f"color:{'#2a9d8f' if ok else '#c1121f'};")

    def _on_new_alert(self, alert):
        self.alerts[alert["id"]] = alert
        self._refresh_table()
        self._refresh_stats()
        self._push_alert_to_map(alert)
        # Signalement sonore/visuel possible ici (notification).

    def _on_alert_updated(self, alert):
        self.alerts[alert["id"]] = alert
        self._refresh_table()
        self._refresh_stats()
        self._push_alert_to_map(alert)

    # ---- Tableau ----
    def _refresh_table(self):
        rows = sorted(self.alerts.values(), key=lambda a: a["created_at"], reverse=True)
        self.table.setRowCount(len(rows))
        for i, a in enumerate(rows):
            values = [
                a.get("time", "—"),
                (a.get("type") or "").capitalize(),
                a.get("neighborhood") or "—",
                f"{round(a['distance_m'])} m" if a.get("distance_m") is not None else "—",
                (a.get("urgency") or "").capitalize(),
                (a.get("status") or "").capitalize(),
            ]
            for j, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if j == 4:  # colonne urgence -> couleur
                    item.setForeground(QColor(URGENCY_COLORS.get(a.get("urgency"), "#000")))
                item.setData(Qt.UserRole, a["id"])
                self.table.setItem(i, j, item)

    def _selected_alert_id(self):
        items = self.table.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _on_row_selected(self):
        pass  # espace réservé pour un panneau de détails futur

    # ---- Statistiques + graphique ----
    def _refresh_stats(self):
        try:
            stats = self.api.get_stats()
        except Exception:
            return
        self.card_today.set_value(stats["today_count"])
        self.card_active.set_value(stats["active_count"])
        self.card_zones.set_value(len(stats["dangerous_zones"]))
        self.card_last.set_value(stats["total_count"])

        by_type = stats.get("by_type", {})
        categories = list(by_type.keys())
        self.bar_set.remove(0, self.bar_set.count())
        for cat in categories:
            self.bar_set.append(by_type[cat])
        self.axis_x.clear()
        self.axis_x.append([c.capitalize() for c in categories])
        max_val = max(by_type.values()) if by_type else 1
        self.axis_y.setRange(0, max(1, max_val))

    # ---- Carte ----
    def _on_map_loaded(self, ok):
        self.map_ready = ok
        if ok:
            self._push_all_to_map()

    def _push_all_to_map(self):
        data = json.dumps(list(self.alerts.values()))
        self.map_view.page().runJavaScript(f"window.setAlerts({data});")

    def _push_alert_to_map(self, alert):
        if self.map_ready:
            self.map_view.page().runJavaScript(f"window.addAlert({json.dumps(alert)});")

    def _focus_selected_on_map(self):
        aid = self._selected_alert_id()
        if aid and self.map_ready:
            self.map_view.page().runJavaScript(f"window.focusAlert({aid});")

    # ---- Actions opérateur ----
    def _assign_selected(self):
        aid = self._selected_alert_id()
        if not aid:
            QMessageBox.information(self, "Info", "Sélectionnez d'abord une alerte.")
            return
        if not self.teams:
            QMessageBox.warning(self, "Info", "Aucune équipe disponible.")
            return
        # Petit dialogue de choix d'équipe.
        dlg = QDialog(self)
        dlg.setWindowTitle("Affecter une équipe")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Choisir l'équipe d'intervention :"))
        combo = QComboBox()
        for t in self.teams:
            combo.addItem(f"{t['name']} ({t['status']})", t["id"])
        lay.addWidget(combo)
        ok = QPushButton("Affecter")
        ok.clicked.connect(dlg.accept)
        lay.addWidget(ok)
        if dlg.exec() == QDialog.Accepted:
            try:
                updated = self.api.assign_team(aid, combo.currentData())
                self._on_alert_updated(updated)
                self.teams = self.api.get_teams()
            except Exception as e:
                QMessageBox.warning(self, "Erreur", str(e))

    def _close_selected(self):
        aid = self._selected_alert_id()
        if not aid:
            QMessageBox.information(self, "Info", "Sélectionnez d'abord une alerte.")
            return
        if QMessageBox.question(self, "Clôturer", "Clôturer cette alerte ?") == QMessageBox.Yes:
            try:
                updated = self.api.close_alert(aid)
                self._on_alert_updated(updated)
                self.teams = self.api.get_teams()
            except Exception as e:
                QMessageBox.warning(self, "Erreur", str(e))


def main():
    app = QApplication(sys.argv)
    api = ApiClient(API_BASE)

    login = LoginDialog(api)
    if login.exec() != QDialog.Accepted:
        sys.exit(0)

    window = MainWindow(api, login.user or {"name": "Opérateur"})
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
