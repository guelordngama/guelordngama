"""SafeCity — Poste opérateur (centre de commandement).

Interface PySide6 moderne, thème sombre :
  - Menu latéral (tableau de bord, alertes, carte, agents, citoyens, historique,
    statistiques, rapports, paramètres, déconnexion)
  - Tableau de bord (tuiles, graphiques, dernières alertes)
  - Pop-up d'incident à l'arrivée d'une alerte (alarme sonore + actions)
  - Carte interactive colorée par gravité + positions des patrouilles

Lancement :
    python -m desktop.main
    python desktop/main.py
"""
import os
import sys

# Import robuste : ajoute le dossier au chemin puis imports absolus.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import theme
from api_client import ApiClient
from pages import (
    DashboardPage,
    HistoryPage,
    LiveAlertsPage,
    MapPage,
    PeoplePage,
    ReportsPage,
    SettingsPage,
    StatisticsPage,
)
from sound import AlarmPlayer
from widgets import IncidentPopup, Toast

API_BASE = os.environ.get("SAFECITY_API", "http://127.0.0.1:5000")


# --------------------------------------------------------------------------- #
# Pont temps réel Socket.IO -> signaux Qt
# --------------------------------------------------------------------------- #
class RealtimeBridge(QThread):
    new_alert = Signal(dict)
    alert_updated = Signal(dict)
    connection_changed = Signal(bool)
    agents_count = Signal(int)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        self.api.on("new_alert", lambda d: self.new_alert.emit(d))
        self.api.on("alert_updated", lambda d: self.alert_updated.emit(d))
        self.api.on("connect", lambda: self.connection_changed.emit(True))
        self.api.on("disconnect", lambda: self.connection_changed.emit(False))
        self.api.on("agents_count", lambda d: self.agents_count.emit(d.get("count", 0)))
        self.api.connect_realtime()


# --------------------------------------------------------------------------- #
# Connexion
# --------------------------------------------------------------------------- #
class LoginDialog(QDialog):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user = None
        self.setWindowTitle("SafeCity — Connexion")
        self.setMinimumWidth(380)
        self.setStyleSheet(theme.QSS + f"QDialog {{ background: {theme.BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(6)

        brand = QLabel("🛡️  SafeCity")
        brand.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {theme.TEXT};")
        sub = QLabel("Centre de surveillance — Mairie")
        sub.setObjectName("muted")
        root.addWidget(brand)
        root.addWidget(sub)
        root.addSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        self.email = QLineEdit("operateur@safecity.local")
        self.password = QLineEdit("safecity123")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.returnPressed.connect(self._try_login)
        form.addRow("Email", self.email)
        form.addRow("Mot de passe", self.password)
        root.addLayout(form)

        btn = QPushButton("Se connecter")
        btn.clicked.connect(self._try_login)
        root.addSpacing(6)
        root.addWidget(btn)

        self.info = QLabel("Compte de démonstration pré-rempli.")
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        root.addWidget(self.info)

    def _try_login(self):
        try:
            self.user = self.api.login(self.email.text().strip(), self.password.text())
            self.accept()
        except Exception as e:
            self.info.setText("Échec : " + str(e))
            self.info.setStyleSheet("color: #ff8181;")


# --------------------------------------------------------------------------- #
# Menu latéral
# --------------------------------------------------------------------------- #
class Sidebar(QFrame):
    navigate = Signal(int)
    logout = Signal()

    ITEMS = [
        ("🏠", "Tableau de bord"),
        ("🚨", "Alertes en direct"),
        ("🗺️", "Carte interactive"),
        ("👮", "Gestion des agents"),
        ("👥", "Gestion des citoyens"),
        ("📜", "Historique"),
        ("📊", "Statistiques"),
        ("📄", "Rapports"),
        ("⚙️", "Paramètres"),
    ]

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(248)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 18, 14, 14)
        root.setSpacing(6)

        brand = QLabel("🛡️ SafeCity")
        brand.setObjectName("brand")
        sub = QLabel("Centre de commandement")
        sub.setObjectName("brandSub")
        root.addWidget(brand)
        root.addWidget(sub)
        root.addSpacing(16)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (icon, label) in enumerate(self.ITEMS):
            b = QPushButton(f"  {icon}   {label}")
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self.navigate.emit(idx))
            self.group.addButton(b, i)
            root.addWidget(b)
        self.group.button(0).setChecked(True)

        root.addStretch()
        self.badge = QLabel("● Hors ligne")
        self.badge.setStyleSheet("color: #ff8181; font-weight: 700; padding: 6px 10px;")
        root.addWidget(self.badge)

        logout = QPushButton("  🔒   Déconnexion")
        logout.setObjectName("logoutBtn")
        logout.setCursor(Qt.PointingHandCursor)
        logout.clicked.connect(self.logout.emit)
        root.addWidget(logout)

    def set_online(self, ok):
        self.badge.setText("● En ligne" if ok else "● Hors ligne")
        self.badge.setStyleSheet(
            f"color: {'#22c55e' if ok else '#ff8181'}; font-weight: 700; padding: 6px 10px;"
        )

    def select(self, idx):
        self.group.button(idx).setChecked(True)


# --------------------------------------------------------------------------- #
# Fenêtre principale
# --------------------------------------------------------------------------- #
class MainWindow(QWidget):
    def __init__(self, api, operator):
        super().__init__()
        self.api = api
        self.operator = operator
        self.alerts = {}
        self.teams = []
        self._open_popups = {}

        self.setObjectName("root")
        self.setWindowTitle("SafeCity — Centre de commandement")
        self.resize(1320, 860)
        self.setStyleSheet(theme.QSS)
        self.alarm = AlarmPlayer()

        self._build_ui()
        self._load_initial()
        self._start_realtime()

        # Rafraîchissement périodique (filet de sécurité en plus du temps réel).
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_stats)
        self._timer.start(15000)

    # ---- Construction ----
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self._navigate)
        self.sidebar.logout.connect(self._logout)
        root.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        # Barre supérieure
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(64)
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(24, 0, 24, 0)
        self.page_title = QLabel("Tableau de bord")
        self.page_title.setObjectName("pageTitle")
        tl.addWidget(self.page_title)
        tl.addStretch()
        self.clock = QLabel("")
        self.clock.setObjectName("clock")
        tl.addWidget(self.clock)
        tl.addSpacing(16)
        who = QLabel(f"👮 {self.operator.get('name', '—')}  ·  {self.operator.get('role', '')}")
        who.setStyleSheet("font-weight: 700;")
        tl.addWidget(who)
        right.addWidget(topbar)

        # Horloge
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

        # Pages empilées
        self.stack = QStackedWidget()
        self.page_dashboard = DashboardPage()
        self.page_live = LiveAlertsPage()
        self.page_map = MapPage()
        self.page_agents = PeoplePage(["Nom", "Rôle", "Email", "Statut"])
        self.page_citizens = PeoplePage(["Nom", "Téléphone", "Email", "Inscrit le"])
        self.page_history = HistoryPage()
        self.page_stats = StatisticsPage()
        self.page_reports = ReportsPage()
        self.page_settings = SettingsPage(API_BASE, self.operator)
        for p in (
            self.page_dashboard, self.page_live, self.page_map, self.page_agents,
            self.page_citizens, self.page_history, self.page_stats, self.page_reports,
            self.page_settings,
        ):
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)

        # Connexions inter-pages
        self.page_dashboard.go_to_map.connect(lambda: self._navigate(2))
        self.page_dashboard.request_focus.connect(self._focus_on_map)
        self.page_live.request_assign.connect(self._assign)
        self.page_live.request_close.connect(self._close)
        self.page_live.request_focus.connect(self._focus_on_map)
        self.page_live.open_incident.connect(self._open_incident_by_id)

    def _tick_clock(self):
        from datetime import datetime

        self.clock.setText(datetime.now().strftime("%A %d %B %Y · %H:%M:%S"))

    # ---- Navigation ----
    def _navigate(self, idx):
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(idx)
        self.page_title.setText(Sidebar.ITEMS[idx][1])
        if idx == 3:
            self._load_agents()
        elif idx == 4:
            self._load_citizens()

    # ---- Chargement initial ----
    def _load_initial(self):
        try:
            self.teams = self.api.get_teams()
            for a in self.api.get_alerts():
                self.alerts[a["id"]] = a
            self._refresh_all()
            self.page_map.set_patrols(self.teams)
        except Exception as e:
            QMessageBox.warning(self, "Erreur réseau", f"Chargement impossible :\n{e}")

    def _load_agents(self):
        try:
            rows = []
            for u in self.api.get_agents():
                status = "● Actif" if u.get("active") else "○ Inactif"
                rows.append([
                    (u["name"], None),
                    (u["role"].capitalize(), theme.ACCENT_2),
                    (u.get("email") or "—", None),
                    (status, "#22c55e" if u.get("active") else theme.MUTED),
                ])
            self.page_agents.set_rows(rows)
        except Exception as e:
            QMessageBox.warning(self, "Agents", str(e))

    def _load_citizens(self):
        try:
            rows = []
            for u in self.api.get_citizens():
                rows.append([
                    (u["name"], None),
                    (u.get("phone") or "—", None),
                    (u.get("email") or "—", None),
                    ((u.get("created_at") or "")[:10], theme.MUTED),
                ])
            self.page_citizens.set_rows(rows)
        except Exception as e:
            QMessageBox.warning(self, "Citoyens", str(e))

    # ---- Temps réel ----
    def _start_realtime(self):
        self.bridge = RealtimeBridge(self.api)
        self.bridge.new_alert.connect(self._on_new_alert)
        self.bridge.alert_updated.connect(self._on_alert_updated)
        self.bridge.connection_changed.connect(self.sidebar.set_online)
        self.bridge.start()

    def _on_new_alert(self, alert):
        self.alerts[alert["id"]] = alert
        self._refresh_all()
        self.page_map.add_alert(alert)
        # Notification sonore + visuelle + pop-up d'incident
        self.alarm.play()
        Toast(self, f"Nouvelle alerte : {alert['type'].capitalize()} ({theme.urgency_label(alert['urgency'])})",
              theme.urgency_color(alert["urgency"])).show_for(5000)
        self._open_incident(alert)

    def _on_alert_updated(self, alert):
        self.alerts[alert["id"]] = alert
        self._refresh_all()
        self.page_map.add_alert(alert)

    # ---- Rafraîchissement ----
    def _sorted_alerts(self):
        return sorted(self.alerts.values(), key=lambda a: a["created_at"], reverse=True)

    def _refresh_all(self):
        alerts = self._sorted_alerts()
        self.page_dashboard.set_alerts(alerts)
        self.page_live.set_alerts(alerts)
        self.page_history.set_alerts(alerts)
        self.page_map.set_alerts(alerts)
        self._refresh_stats()

    def _refresh_stats(self):
        try:
            stats = self.api.get_stats()
        except Exception:
            return
        self.page_dashboard.set_stats(stats)
        self.page_stats.set_stats(stats)
        self.page_reports.set_stats(stats)

    # ---- Incident pop-up ----
    def _open_incident(self, alert):
        if alert["id"] in self._open_popups:
            return
        popup = IncidentPopup(alert, self)
        popup.setStyleSheet(theme.QSS)
        popup.accept_incident.connect(lambda a: Toast(self, "Incident accepté", theme.ACCENT).show_for(2500))
        popup.send_patrol.connect(self._assign_alert)
        popup.open_on_map.connect(lambda a: (self._navigate(2), self._focus_on_map(a["id"])))
        popup.close_incident.connect(lambda a: self._close(a["id"]))
        popup.finished.connect(lambda _=0, aid=alert["id"]: self._open_popups.pop(aid, None))
        self._open_popups[alert["id"]] = popup
        popup.show()
        popup.raise_()
        popup.activateWindow()

    def _open_incident_by_id(self, alert_id):
        alert = self.alerts.get(alert_id)
        if alert:
            self._open_incident(alert)

    # ---- Actions opérateur ----
    def _focus_on_map(self, alert_id):
        self._navigate(2)
        self.page_map.focus(alert_id)

    def _assign(self, alert_id):
        alert = self.alerts.get(alert_id)
        if alert:
            self._assign_alert(alert)

    def _assign_alert(self, alert):
        if not self.teams:
            QMessageBox.information(self, "Info", "Aucune équipe disponible.")
            return
        dlg = QDialog(self)
        dlg.setStyleSheet(theme.QSS)
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
                updated = self.api.assign_team(alert["id"], combo.currentData())
                self._on_alert_updated(updated)
                self.teams = self.api.get_teams()
                self.page_map.set_patrols(self.teams)
                Toast(self, "Équipe affectée 🚔", "#eab308").show_for(2500)
            except Exception as e:
                QMessageBox.warning(self, "Erreur", str(e))

    def _close(self, alert_id):
        if QMessageBox.question(self, "Clôturer", "Clôturer cette alerte ?") != QMessageBox.Yes:
            return
        try:
            updated = self.api.close_alert(alert_id)
            self._on_alert_updated(updated)
            self.teams = self.api.get_teams()
            self.page_map.set_patrols(self.teams)
            Toast(self, "Incident clôturé ✅", "#22c55e").show_for(2500)
        except Exception as e:
            QMessageBox.warning(self, "Erreur", str(e))

    def _logout(self):
        if QMessageBox.question(self, "Déconnexion", "Se déconnecter ?") == QMessageBox.Yes:
            self.close()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.QSS)
    api = ApiClient(API_BASE)

    login = LoginDialog(api)
    if login.exec() != QDialog.Accepted:
        sys.exit(0)

    window = MainWindow(api, login.user or {"name": "Opérateur", "role": "operator"})
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
