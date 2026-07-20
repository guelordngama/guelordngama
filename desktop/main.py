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
    AboutPage,
    AgentsPage,
    AnalyticsPage,
    ChatPage,
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
from widgets import AgentDialog, IncidentPopup, Toast

API_BASE = os.environ.get("SAFECITY_API", "http://127.0.0.1:5000")


# --------------------------------------------------------------------------- #
# Pont temps réel Socket.IO -> signaux Qt
# --------------------------------------------------------------------------- #
class RealtimeBridge(QThread):
    new_alert = Signal(dict)
    alert_updated = Signal(dict)
    connection_changed = Signal(bool)
    agents_count = Signal(int)
    agent_updated = Signal(dict)
    agent_deleted = Signal(int)
    chat_message = Signal(dict)

    def __init__(self, api):
        super().__init__()
        self.api = api

    def run(self):
        self.api.on("new_alert", lambda d: self.new_alert.emit(d))
        self.api.on("alert_updated", lambda d: self.alert_updated.emit(d))
        self.api.on("connect", lambda: self.connection_changed.emit(True))
        self.api.on("disconnect", lambda: self.connection_changed.emit(False))
        self.api.on("agents_count", lambda d: self.agents_count.emit(d.get("count", 0)))
        self.api.on("agent_updated", lambda d: self.agent_updated.emit(d))
        self.api.on("agent_deleted", lambda d: self.agent_deleted.emit(d.get("id")))
        self.api.on("chat_message", lambda d: self.chat_message.emit(d))
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
        ("📈", "Performances"),
        ("📄", "Rapports"),
        ("💬", "Messagerie"),
        ("⚙️", "Paramètres"),
        ("ℹ️", "À propos"),
    ]

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(280)
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
        self._base_text = {}     # idx -> texte de base du bouton
        self._unread = {}        # idx -> compteur non lus
        for i, (icon, label) in enumerate(self.ITEMS):
            base = f"  {icon}   {label}"
            self._base_text[i] = base
            self._unread[i] = 0
            b = QPushButton(base)
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

    # ---- Badges de notification « non lu » ----
    def bump(self, idx, n=1):
        self._unread[idx] = self._unread.get(idx, 0) + n
        self._refresh_badge(idx)

    def clear_badge(self, idx):
        if self._unread.get(idx):
            self._unread[idx] = 0
            self._refresh_badge(idx)

    def _refresh_badge(self, idx):
        btn = self.group.button(idx)
        if not btn:
            return
        count = self._unread.get(idx, 0)
        badge = f"  🔴{count if count < 100 else '99+'}" if count else ""
        btn.setText(self._base_text[idx] + badge)


# --------------------------------------------------------------------------- #
# Fenêtre principale
# --------------------------------------------------------------------------- #
class MainWindow(QWidget):
    # Index des menus (voir Sidebar.ITEMS)
    IDX_ALERTS = 1
    IDX_MAP = 2
    IDX_AGENTS = 3
    IDX_CHAT = 9

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
        self.page_agents = AgentsPage()
        self.page_citizens = PeoplePage(["Nom", "Téléphone", "Email", "Inscrit le"])
        self.page_history = HistoryPage()
        self.page_stats = StatisticsPage()
        self.page_analytics = AnalyticsPage()
        self.page_reports = ReportsPage()
        self.page_chat = ChatPage(self.operator, API_BASE)
        self.page_settings = SettingsPage(API_BASE, self.operator)
        self.page_about = AboutPage()
        for p in (
            self.page_dashboard, self.page_live, self.page_map, self.page_agents,
            self.page_citizens, self.page_history, self.page_stats, self.page_analytics,
            self.page_reports, self.page_chat, self.page_settings, self.page_about,
        ):
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)

        # Connexions inter-pages
        self.page_dashboard.go_to_map.connect(lambda: self._navigate(2))
        self.page_dashboard.request_focus.connect(self._focus_on_map)
        self.page_live.request_assign.connect(self._assign)
        self.page_live.request_assign_agent.connect(self._assign_agent_to_alert)
        self.page_live.request_close.connect(self._close)
        self.page_live.request_focus.connect(self._focus_on_map)
        self.page_live.open_incident.connect(self._open_incident_by_id)
        self.page_live.search.connect(self._search_alerts)
        self.page_live.reset_search.connect(lambda: self.page_live.set_alerts(self._sorted_alerts()))
        self.page_reports.generate_pdf.connect(self._generate_report)
        self.page_analytics.period_changed.connect(self._load_analytics)
        self.page_agents.request_add.connect(self._add_agent)
        self.page_agents.request_edit.connect(self._edit_agent)
        self.page_agents.request_delete.connect(self._delete_agent)
        self.page_agents.request_locate.connect(self._locate_agent)
        self.page_agents.request_route.connect(self._route_agent)
        self.page_chat.send.connect(self._send_message)
        self.page_history.export_csv.connect(lambda: self._export_history("csv"))
        self.page_history.export_xlsx.connect(lambda: self._export_history("xlsx"))

    def _tick_clock(self):
        from datetime import datetime

        self.clock.setText(datetime.now().strftime("%A %d %B %Y · %H:%M:%S"))

    # ---- Navigation ----
    def _navigate(self, idx):
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(idx)
        self.sidebar.clear_badge(idx)  # consulter la section efface son badge
        self.page_title.setText(Sidebar.ITEMS[idx][1])
        if idx == 3:
            self._load_agents()
        elif idx == 4:
            self._load_citizens()
        elif idx == 7:
            self._load_analytics(self.page_analytics.period.currentData())
        elif idx == 9:
            self._load_messages()

    # ---- Chargement initial ----
    def _load_initial(self):
        try:
            self.teams = self.api.get_teams()
            for a in self.api.get_alerts():
                self.alerts[a["id"]] = a
            self._refresh_all()
            self.page_map.set_patrols(self.teams)
            self._load_agents()  # agents + marqueurs carte
        except Exception as e:
            QMessageBox.warning(self, "Erreur réseau", f"Chargement impossible :\n{e}")

    def _load_agents(self):
        try:
            agents = self.api.get_agents()
            self.page_agents.set_agents(agents)
            self.page_map.set_agents(agents)
        except Exception as e:
            QMessageBox.warning(self, "Agents", str(e))

    def _load_analytics(self, period):
        try:
            self.page_analytics.set_data(self.api.get_analytics(period))
        except Exception as e:
            QMessageBox.warning(self, "Performances", str(e))

    def _search_alerts(self, filters):
        try:
            result = self.api.get_alerts(filters=filters)
            items = result.get("items", result) if isinstance(result, dict) else result
            self.page_live.set_alerts(items, searching=True)
        except Exception as e:
            QMessageBox.warning(self, "Recherche", str(e))

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
        self.bridge.agent_updated.connect(self._on_agent_updated)
        self.bridge.start()

        self.bridge.agent_deleted.connect(self._on_agent_deleted)
        self.bridge.chat_message.connect(self._on_chat_message)

    def _on_agent_updated(self, agent):
        # Détecte un changement significatif (nouvel agent ou changement de
        # disponibilité) pour n'alerter que sur l'essentiel, pas sur chaque
        # rafraîchissement de position GPS.
        prev = self.page_agents.agents.get(agent["id"])
        significant = prev is None or prev.get("availability") != agent.get("availability")
        self.page_agents.update_agent(agent)
        try:
            self.page_map.set_agents(list(self.page_agents.agents.values()))
        except Exception:
            pass
        if significant and self.stack.currentIndex() != self.IDX_AGENTS:
            self.sidebar.bump(self.IDX_AGENTS)

    def _on_agent_deleted(self, agent_id):
        self.page_agents.remove_agent(agent_id)
        self.page_map.set_agents(list(self.page_agents.agents.values()))
        if self.stack.currentIndex() != self.IDX_AGENTS:
            self.sidebar.bump(self.IDX_AGENTS)

    # ---- Messagerie ----
    def _load_messages(self):
        try:
            self.page_chat.set_messages(self.api.get_messages(50))
        except Exception as e:
            QMessageBox.warning(self, "Messagerie", str(e))

    def _send_message(self, text, attachment=""):
        try:
            self.api.send_message(text, attachment=attachment or None)
        except Exception as e:
            QMessageBox.warning(self, "Messagerie", str(e))

    def _on_chat_message(self, msg):
        self.page_chat.add_message(msg)
        # Notification + badge « non lu » si on n'est pas sur la page Messagerie
        # et que le message vient d'un autre utilisateur.
        if self.stack.currentIndex() != self.IDX_CHAT and msg.get("sender_id") != self.operator.get("id"):
            self.sidebar.bump(self.IDX_CHAT)
            Toast(self, f"💬 {msg.get('sender_name')}: {msg.get('text', '')[:40]}", theme.ACCENT_2).show_for(3500)

    # ---- Export de l'historique ----
    def _export_history(self, fmt):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl as _QUrl
        from PySide6.QtWidgets import QFileDialog

        ext = "xlsx" if fmt == "xlsx" else "csv"
        default = os.path.join(os.path.expanduser("~"), f"safecity_alertes.{ext}")
        path, _ = QFileDialog.getSaveFileName(self, "Exporter l'historique", default,
                                              f"{ext.upper()} (*.{ext})")
        if not path:
            return
        try:
            self.api.download_export(ext, path)
            QDesktopServices.openUrl(_QUrl.fromLocalFile(path))
            Toast(self, f"Historique exporté ({ext.upper()}) ⬇️", "#22c55e").show_for(3000)
        except Exception as e:
            QMessageBox.warning(self, "Export", str(e))

    # ---- Gestion des agents (CRUD) ----
    def _add_agent(self):
        dlg = AgentDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            try:
                self.api.create_agent(dlg.payload())
                self._load_agents()
                Toast(self, "Agent ajouté ➕", "#22c55e").show_for(2500)
            except Exception as e:
                QMessageBox.warning(self, "Ajout d'agent", str(e))

    def _edit_agent(self, agent):
        dlg = AgentDialog(agent=agent, parent=self)
        if dlg.exec() == QDialog.Accepted:
            try:
                self.api.update_agent(agent["id"], dlg.payload())
                self._load_agents()
                Toast(self, "Agent modifié ✏️", theme.ACCENT).show_for(2500)
            except Exception as e:
                QMessageBox.warning(self, "Modification d'agent", str(e))

    def _delete_agent(self, agent):
        if QMessageBox.question(
            self, "Supprimer l'agent",
            f"Supprimer définitivement « {agent['name']} » ?",
        ) != QMessageBox.Yes:
            return
        try:
            self.api.delete_agent(agent["id"])
            self.page_agents.remove_agent(agent["id"])
            self.page_map.set_agents(list(self.page_agents.agents.values()))
            Toast(self, "Agent supprimé 🗑️", "#ef4444").show_for(2500)
        except Exception as e:
            QMessageBox.warning(self, "Suppression d'agent", str(e))

    def _locate_agent(self, agent):
        if agent.get("lat") is None or agent.get("lng") is None:
            QMessageBox.information(
                self, "Localisation",
                f"La position de « {agent['name']} » n'est pas encore disponible.\n"
                "L'agent doit être connecté au portail (position GPS active).")
            return
        self._navigate(2)  # carte
        self.page_map.set_agents(list(self.page_agents.agents.values()))
        self.page_map.focus_agent(agent["lat"], agent["lng"])

    def _route_agent(self, agent):
        """Trace l'itinéraire le plus rapide entre l'agent et son intervention."""
        if agent.get("lat") is None or agent.get("lng") is None:
            QMessageBox.information(self, "Itinéraire",
                                    f"Position de « {agent['name']} » indisponible.")
            return
        alert_id = agent.get("current_alert_id")
        alert = self.alerts.get(alert_id) if alert_id else None
        if not alert:
            QMessageBox.information(
                self, "Itinéraire",
                f"« {agent['name']} » n'a pas d'intervention en cours.\n"
                "L'itinéraire est tracé entre un agent et l'incident qu'il traite.")
            return
        self._navigate(2)
        self.page_map.set_agents(list(self.page_agents.agents.values()))
        self.page_map.show_route(agent["lat"], agent["lng"], alert["lat"], alert["lng"])
        Toast(self, "Itinéraire le plus rapide tracé 🧭", theme.ACCENT).show_for(2500)

    def _on_new_alert(self, alert):
        self.alerts[alert["id"]] = alert
        self._refresh_all()
        self.page_map.add_alert(alert)
        # Notification sonore + visuelle + pop-up d'incident
        self.alarm.play()
        # Badge « non lu » sur « Alertes en direct » si on ne la consulte pas.
        if self.stack.currentIndex() != self.IDX_ALERTS:
            self.sidebar.bump(self.IDX_ALERTS)
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
        popup.accept_incident.connect(self._acknowledge_incident)
        popup.send_patrol.connect(self._assign_alert)
        popup.assign_agent.connect(lambda a: self._assign_agent_to_alert(a["id"]))
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

    def _acknowledge_incident(self, alert):
        """Alerte prise en compte par l'opérateur : son d'accusé de réception."""
        self.alarm.play_ack()
        Toast(self, "✅ Incident pris en compte", "#22c55e").show_for(2500)

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
                self.alarm.play_ack()  # accusé de réception : alerte prise en compte
                Toast(self, "Équipe affectée 🚔", "#eab308").show_for(2500)
            except Exception as e:
                QMessageBox.warning(self, "Erreur", str(e))

    def _assign_agent_to_alert(self, alert_id):
        """L'opérateur assigne l'alerte sélectionnée à un agent précis."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return
        agents = [a for a in self.page_agents.agents.values() if a.get("role") == "agent"]
        if not agents:
            try:
                agents = [a for a in self.api.get_agents() if a.get("role") == "agent"]
            except Exception as e:
                QMessageBox.warning(self, "Agents", str(e))
                return
        if not agents:
            QMessageBox.information(self, "Info", "Aucun agent disponible.")
            return
        dlg = QDialog(self)
        dlg.setStyleSheet(theme.QSS)
        dlg.setWindowTitle("Affecter un agent")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Assigner l'alerte « {alert['type'].capitalize()} » "
                             f"({theme.urgency_label(alert['urgency'])}) à :"))
        combo = QComboBox()
        for a in sorted(agents, key=lambda x: x.get("availability") != "available"):
            dispo = {"available": "🟢", "busy": "🟠", "offline": "⚫"}.get(a.get("availability"), "")
            combo.addItem(f"{dispo} {a['name']}", a["id"])
        lay.addWidget(combo)
        ok = QPushButton("Affecter l'agent")
        ok.clicked.connect(dlg.accept)
        lay.addWidget(ok)
        if dlg.exec() == QDialog.Accepted:
            try:
                updated = self.api.assign_agent(alert_id, combo.currentData())
                self._on_alert_updated(updated)
                self._load_agents()
                self.alarm.play_ack()
                Toast(self, "Agent assigné 👮", "#eab308").show_for(2500)
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

    def _generate_report(self, period):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl as _QUrl
        from PySide6.QtWidgets import QFileDialog

        default = os.path.join(os.path.expanduser("~"), f"safecity_rapport_{period}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le rapport", default, "PDF (*.pdf)")
        if not path:
            return
        try:
            self.api.download_report(period, path)
            self.page_reports.set_status(f"Rapport enregistré : {path}", ok=True)
            QDesktopServices.openUrl(_QUrl.fromLocalFile(path))  # ouvre le PDF
            Toast(self, "Rapport PDF généré 📄", "#22c55e").show_for(3000)
        except Exception as e:
            self.page_reports.set_status(f"Échec : {e}", ok=False)
            QMessageBox.warning(self, "Rapport", str(e))

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
