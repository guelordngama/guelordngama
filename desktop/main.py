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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
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


def app_icon():
    """Icône d'application (bouclier SafeCity) rendue à la volée, sans fichier."""
    from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap

    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, 0, 64)
    grad.setColorAt(0, QColor("#3d8bff"))
    grad.setColorAt(1, QColor("#1e40af"))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(10, 8, 44, 48, 12, 12)
    f = QFont(); f.setPointSize(24); f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(pm.rect(), Qt.AlignCenter, "🛡")
    p.end()
    return QIcon(pm)


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
def _api_error_message(exc):
    """Extrait le message lisible d'une erreur ApiClient (format « 409: {json} »)."""
    import json as _json
    import re as _re

    s = str(exc)
    m = _re.search(r"\{.*\}", s, _re.DOTALL)
    if m:
        try:
            return _json.loads(m.group(0)).get("error", {}).get("message") or s
        except Exception:
            pass
    return s


class LoginDialog(QDialog):
    """Connexion + création de compte (opérateur) + mot de passe oublié."""

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user = None
        self.setWindowTitle("SafeCity — Connexion")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(400)
        self.setStyleSheet(theme.QSS + f"""
            QDialog {{ background: {theme.BG}; }}
            QTabWidget::pane {{ border: 1px solid {theme.BORDER}; border-radius: 10px;
                                background: {theme.BG}; top: -1px; }}
            QTabBar::tab {{ background: {theme.PANEL}; color: {theme.MUTED};
                           padding: 8px 18px; margin-right: 4px;
                           border-top-left-radius: 8px; border-top-right-radius: 8px; }}
            QTabBar::tab:selected {{ background: {theme.ACCENT}; color: white; font-weight: 700; }}
            QPushButton#linkBtn {{ background: transparent; color: {theme.ACCENT};
                                   border: none; font-weight: 600; padding: 2px; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(6)

        brand = QLabel("🛡️  SafeCity")
        brand.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {theme.TEXT};")
        sub = QLabel("Centre de surveillance — Mairie")
        sub.setObjectName("muted")
        root.addWidget(brand)
        root.addWidget(sub)
        root.addSpacing(12)

        tabs = QTabWidget()
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(True)
        tabs.addTab(self._build_login_tab(), "Se connecter")
        tabs.addTab(self._build_register_tab(), "Créer un compte")
        root.addWidget(tabs)

        self.info = QLabel("Compte de démonstration pré-rempli.")
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        root.addWidget(self.info)

    # ---- Onglet Connexion ----
    def _build_login_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(2, 12, 2, 6)
        lay.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)
        self.email = QLineEdit("operateur@safecity.local")
        self.password = QLineEdit("safecity123")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.returnPressed.connect(self._try_login)
        form.addRow("Email", self.email)
        form.addRow("Mot de passe", self._pw_field(self.password))
        lay.addLayout(form)

        self.btn_login = QPushButton("Se connecter")
        self.btn_login.clicked.connect(self._try_login)
        lay.addWidget(self.btn_login)

        forgot = QPushButton("Mot de passe oublié ?")
        forgot.setObjectName("linkBtn")
        forgot.setCursor(Qt.PointingHandCursor)
        forgot.setFlat(True)
        forgot.clicked.connect(self._forgot_password)
        lay.addWidget(forgot, alignment=Qt.AlignRight)
        return w

    # ---- Onglet Créer un compte ----
    def _build_register_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(2, 12, 2, 6)
        lay.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)
        self.r_name = QLineEdit()
        self.r_name.setPlaceholderText("Nom et prénom")
        self.r_email = QLineEdit()
        self.r_email.setPlaceholderText("vous@exemple.com")
        self.r_phone = QLineEdit()
        self.r_phone.setPlaceholderText("+243 … (optionnel)")
        self.r_pass = QLineEdit()
        self.r_pass.setEchoMode(QLineEdit.Password)
        self.r_pass.setPlaceholderText("Au moins 6 caractères")
        self.r_pass2 = QLineEdit()
        self.r_pass2.setEchoMode(QLineEdit.Password)
        self.r_pass2.setPlaceholderText("Confirmer le mot de passe")
        self.r_invite = QLineEdit()
        self.r_invite.setPlaceholderText("Fourni par l'administrateur")
        self.r_invite.returnPressed.connect(self._try_register)
        form.addRow("Nom", self.r_name)
        form.addRow("Email", self.r_email)
        form.addRow("Téléphone", self.r_phone)
        form.addRow("Mot de passe", self._pw_field(self.r_pass))
        form.addRow("Confirmer", self._pw_field(self.r_pass2))
        form.addRow("Code d'invitation", self.r_invite)
        lay.addLayout(form)

        self.btn_register = QPushButton("Créer le compte (opérateur)")
        self.btn_register.setObjectName("success")
        self.btn_register.clicked.connect(self._try_register)
        lay.addWidget(self.btn_register)

        hint = QLabel("Compte de rôle « opérateur ». Un code d'invitation "
                      "(fourni par l'administrateur) est requis.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return w

    # ---- Helpers ----
    @staticmethod
    def _pw_field(field):
        """Enveloppe un champ mot de passe avec un bouton œil (afficher/masquer)."""
        eye = QPushButton("👁️")
        eye.setObjectName("ghost")
        eye.setFixedWidth(42)
        eye.setCheckable(True)
        eye.setCursor(Qt.PointingHandCursor)
        eye.setToolTip("Afficher / masquer le mot de passe")

        def toggle():
            on = eye.isChecked()
            field.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
            eye.setText("🙈" if on else "👁️")

        eye.clicked.connect(toggle)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(field, 1)
        row.addWidget(eye)
        wrap = QWidget()
        wrap.setLayout(row)
        return wrap

    def _set_busy(self, btn, busy, label=None):
        """État « chargement » d'un bouton pendant un appel réseau (bloquant)."""
        if busy:
            btn._orig_text = btn.text()
            btn.setText(label or "Veuillez patienter…")
            btn.setEnabled(False)
        else:
            btn.setText(getattr(btn, "_orig_text", btn.text()))
            btn.setEnabled(True)
        QApplication.processEvents()  # force le repaint avant l'appel bloquant

    # ---- Actions ----
    def _try_login(self):
        self._set_busy(self.btn_login, True, "Connexion…")
        try:
            self.user = self.api.login(self.email.text().strip(), self.password.text())
            self.accept()
        except Exception as e:
            self._error("Échec : " + _api_error_message(e))
        finally:
            self._set_busy(self.btn_login, False)

    def _try_register(self):
        name = self.r_name.text().strip()
        email = self.r_email.text().strip()
        pwd = self.r_pass.text()
        pwd2 = self.r_pass2.text()
        if not name or not email or not pwd:
            self._error("Nom, e-mail et mot de passe sont requis.")
            return
        if pwd != pwd2:
            self._error("Les deux mots de passe ne correspondent pas.")
            return
        self._set_busy(self.btn_register, True, "Création…")
        try:
            self.user = self.api.register_staff(
                name, email, pwd, self.r_phone.text().strip(),
                self.r_invite.text().strip())
            self.accept()
        except Exception as e:
            self._error("Création impossible : " + _api_error_message(e))
        finally:
            self._set_busy(self.btn_register, False)

    def _forgot_password(self):
        default = self.email.text().strip()
        email, ok = QInputDialog.getText(
            self, "Mot de passe oublié",
            "Entrez l'e-mail de votre compte.\nUn mot de passe temporaire sera "
            "envoyé dans votre boîte Gmail :",
            text=default)
        if not ok or not email.strip():
            return
        try:
            res = self.api.forgot_password(email.strip())
            QMessageBox.information(self, "Réinitialisation",
                                    res.get("message", "Demande envoyée. Vérifiez votre boîte Gmail."))
        except Exception as e:
            QMessageBox.warning(self, "Réinitialisation impossible", _api_error_message(e))

    def _error(self, msg):
        self.info.setText(msg)
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

    def set_badge(self, idx, count):
        """Fixe le compteur « non lu » à une valeur absolue (piloté par des ensembles)."""
        self._unread[idx] = max(0, int(count))
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
        # Ensembles d'ids « non lus » (messages reçus / agents modifiés hors page).
        self._unread_msg_ids = set()
        self._unread_agent_ids = set()

        self.setObjectName("root")
        self.setWindowTitle(
            f"SafeCity — Centre de commandement · {operator.get('name', '')}".strip(" ·"))
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1040, 640)
        self.resize(1320, 860)
        self.setStyleSheet(theme.QSS)
        self.alarm = AlarmPlayer()
        # Préférence son (activé par défaut), mémorisée entre sessions.
        from PySide6.QtCore import QSettings
        self.alarm.set_enabled(
            str(QSettings("SafeCity", "Operateur").value("sound", "true")).lower() != "false")

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
        tl.addSpacing(12)
        self.btn_refresh = QPushButton("🔄 Actualiser")
        self.btn_refresh.setObjectName("ghost")
        self.btn_refresh.setToolTip("Actualiser les données (F5)")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._refresh_now)
        tl.addWidget(self.btn_refresh)
        tl.addSpacing(8)
        self.btn_sound = QPushButton("🔊" if self.alarm.enabled else "🔇")
        self.btn_sound.setObjectName("ghost")
        self.btn_sound.setFixedWidth(46)
        self.btn_sound.setToolTip("Activer / couper le son des notifications")
        self.btn_sound.setCursor(Qt.PointingHandCursor)
        self.btn_sound.clicked.connect(self._toggle_sound)
        tl.addWidget(self.btn_sound)
        tl.addSpacing(8)
        self.btn_theme = QPushButton("☀️" if theme.current_mode() == "light" else "🌙")
        self.btn_theme.setObjectName("ghost")
        self.btn_theme.setFixedWidth(46)
        self.btn_theme.setToolTip("Changer de thème (clair / sombre)")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self._toggle_theme)
        tl.addWidget(self.btn_theme)
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

        # Barre d'état (connexion · compteurs · dernière mise à jour).
        statusbar = QFrame()
        statusbar.setObjectName("statusbar")
        statusbar.setFixedHeight(30)
        sl = QHBoxLayout(statusbar)
        sl.setContentsMargins(18, 0, 18, 0)
        self.status_conn = QLabel("● Connexion…")
        self.status_conn.setObjectName("muted")
        sl.addWidget(self.status_conn)
        sl.addStretch()
        self.status_counts = QLabel("")
        self.status_counts.setObjectName("muted")
        sl.addWidget(self.status_counts)
        sl.addSpacing(18)
        self.status_updated = QLabel("")
        self.status_updated.setObjectName("muted")
        sl.addWidget(self.status_updated)
        right.addWidget(statusbar)

        root.addLayout(right, 1)

        self._install_shortcuts()

        # Connexions inter-pages
        self.page_dashboard.go_to_map.connect(lambda: self._navigate(2))
        self.page_dashboard.request_focus.connect(self._focus_on_map)
        self.page_dashboard.navigate.connect(self._navigate)
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
        self.page_agents.request_history.connect(self._agent_history)
        self.page_chat.send.connect(self._send_message)
        self.page_settings.change_password.connect(self._change_password)
        self.page_history.export_csv.connect(lambda: self._export_history("csv"))
        self.page_history.export_xlsx.connect(lambda: self._export_history("xlsx"))

    def _tick_clock(self):
        from datetime import datetime

        self.clock.setText(datetime.now().strftime("%A %d %B %Y · %H:%M:%S"))

    def _toggle_sound(self):
        from PySide6.QtCore import QSettings

        on = not self.alarm.enabled
        self.alarm.set_enabled(on)
        QSettings("SafeCity", "Operateur").setValue("sound", "true" if on else "false")
        self.btn_sound.setText("🔊" if on else "🔇")
        if on:
            self.alarm.play_notify()  # aperçu sonore quand on réactive
        Toast(self, "🔊 Son activé" if on else "🔇 Son coupé", theme.ACCENT).show_for(1500)

    def _install_shortcuts(self):
        """Raccourcis clavier (navigation, rafraîchir, recherche)."""
        from PySide6.QtGui import QKeySequence, QShortcut

        # Ctrl+1..9 et Ctrl+0 → sections du menu.
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self,
                      activated=lambda idx=i - 1: self._navigate(idx))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=lambda: self._navigate(9))
        QShortcut(QKeySequence("F5"), self, activated=self._refresh_now)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self._toggle_sound)

    def _refresh_now(self):
        # Retour visuel sur le bouton pendant l'actualisation (synchrone).
        btn = getattr(self, "btn_refresh", None)
        if btn is not None:
            btn.setEnabled(False)
            btn.setText("⏳ Actualisation…")
            QApplication.processEvents()
        try:
            self._refresh_all()
            idx = self.stack.currentIndex()
            if idx == self.IDX_AGENTS:
                self._load_agents()
            elif idx == self.IDX_CHAT:
                self._load_messages()
        finally:
            if btn is not None:
                btn.setText("🔄 Actualiser")
                btn.setEnabled(True)
        Toast(self, "🔄 Données actualisées", theme.ACCENT).show_for(1200)

    def _focus_search(self):
        self._navigate(self.IDX_ALERTS)
        try:
            self.page_live.search_bar.q.setFocus()
        except Exception:
            pass

    def _toggle_theme(self):
        from PySide6.QtCore import QSettings

        new = "dark" if theme.current_mode() == "light" else "light"
        theme.set_mode(new)
        QSettings("SafeCity", "Operateur").setValue("theme", new)
        # Ré-applique la feuille de style à toute l'application (thème à chaud).
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.QSS)
        self.setStyleSheet(theme.QSS)
        self.btn_theme.setText("☀️" if new == "light" else "🌙")
        # Zones à style « inline » : on les rafraîchit explicitement.
        if hasattr(self.page_chat, "apply_theme"):
            self.page_chat.apply_theme()

    # ---- Navigation ----
    def _navigate(self, idx):
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(idx)
        self.page_title.setText(Sidebar.ITEMS[idx][1])
        if idx == self.IDX_AGENTS:
            self._load_agents()  # affiche puis efface les « non lus » agents
        elif idx == 4:
            self._load_citizens()
        elif idx == 7:
            self._load_analytics(self.page_analytics.period.currentData())
        elif idx == self.IDX_CHAT:
            self._load_messages()  # affiche puis efface les « non lus » messages
        # Les alertes gardent leur marquage par élément (effacé à l'ouverture de
        # chaque incident) ; les autres sections n'ont pas de badge.

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
            # Surligne les agents modifiés hors page, puis efface leur badge.
            self.page_agents.set_unread(self._unread_agent_ids)
            if self._unread_agent_ids:
                self._unread_agent_ids = set()
                self.sidebar.set_badge(self.IDX_AGENTS, 0)
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
        self.bridge.connection_changed.connect(self._set_online)
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
            self._unread_agent_ids.add(agent["id"])
            self.sidebar.set_badge(self.IDX_AGENTS, len(self._unread_agent_ids))

    def _on_agent_deleted(self, agent_id):
        self.page_agents.remove_agent(agent_id)
        self.page_map.set_agents(list(self.page_agents.agents.values()))
        if self.stack.currentIndex() != self.IDX_AGENTS:
            self._unread_agent_ids.add(agent_id)
            self.sidebar.set_badge(self.IDX_AGENTS, len(self._unread_agent_ids))

    # ---- Messagerie ----
    def _load_messages(self):
        try:
            msgs = self.api.get_messages(50)
            # Affiche les messages non lus (surlignés + séparateur), puis efface.
            self.page_chat.set_messages(msgs, unread_ids=set(self._unread_msg_ids))
            if self._unread_msg_ids:
                self._unread_msg_ids = set()
                self.sidebar.set_badge(self.IDX_CHAT, 0)
        except Exception as e:
            QMessageBox.warning(self, "Messagerie", str(e))

    def _send_message(self, text, attachment="", voice="", voice_duration=0):
        try:
            self.api.send_message(text, attachment=attachment or None, voice=voice or None,
                                  voice_duration=voice_duration or None)
        except Exception as e:
            QMessageBox.warning(self, "Messagerie", str(e))

    def _change_password(self, current, new):
        try:
            self.api.change_password(current, new)
            self.page_settings.password_changed_ok()
        except Exception as e:
            self.page_settings.password_change_failed(_api_error_message(e))

    def _on_chat_message(self, msg):
        self.page_chat.add_message(msg)
        # Notification + badge « non lu » si on n'est pas sur la page Messagerie
        # et que le message vient d'un autre utilisateur.
        if self.stack.currentIndex() != self.IDX_CHAT and msg.get("sender_id") != self.operator.get("id"):
            self._unread_msg_ids.add(msg.get("id"))
            self.sidebar.set_badge(self.IDX_CHAT, len(self._unread_msg_ids))
            self.alarm.play_notify()  # son de réception (message)
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

    def _agent_history(self, agent):
        """Affiche l'historique des interventions d'un agent."""
        from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHeaderView,
                                       QTableWidget, QTableWidgetItem)

        try:
            data = self.api.get_agent_interventions(agent["id"])
        except Exception as e:
            QMessageBox.warning(self, "Interventions", str(e))
            return
        dlg = QDialog(self)
        dlg.setStyleSheet(theme.QSS)
        dlg.setWindowTitle(f"Interventions — {agent['name']}")
        dlg.resize(720, 480)
        lay = QVBoxLayout(dlg)
        rt = data.get("avg_response_min")
        summary = QLabel(
            f"<b>{data['agent']['name']}</b> — {data['total']} intervention(s), "
            f"{data['resolved']} résolue(s), temps de réponse moyen "
            f"{rt if rt is not None else '—'} min, "
            f"{round(data['distance_m']/1000, 2)} km parcourus.")
        summary.setStyleSheet("font-size: 14px;")
        lay.addWidget(summary)
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Date", "Type", "Quartier", "Urgence", "Statut", "Distance"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        items = data.get("items", [])
        table.setRowCount(len(items))
        for i, a in enumerate(items):
            cells = [
                (a.get("created_at") or "").replace("T", " ")[:16],
                (a.get("type") or "").capitalize(),
                a.get("neighborhood") or "—",
                theme.urgency_label(a.get("urgency")),
                theme.STATUS_LABELS.get(a.get("status"), a.get("status")),
                f"{round(a['distance_m'])} m" if a.get("distance_m") is not None else "—",
            ]
            for j, text in enumerate(cells):
                it = QTableWidgetItem(str(text))
                if j == 3:
                    it.setForeground(QColor(theme.urgency_color(a.get("urgency"))))
                elif j == 4:
                    it.setForeground(QColor(theme.STATUS_COLORS.get(a.get("status"), "#fff")))
                table.setItem(i, j, it)
        lay.addWidget(table)
        if not items:
            lay.addWidget(QLabel("Aucune intervention pour cet agent."))
        dlg.exec()

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
        # Marque l'alerte « non lue » si on ne consulte pas déjà la liste.
        if self.stack.currentIndex() != self.IDX_ALERTS:
            self.page_live.mark_unread(alert["id"])
        self._refresh_all()  # rend la liste avec le style « non lu »
        self.page_map.add_alert(alert)
        # Notification sonore + visuelle + pop-up d'incident
        self.alarm.play()
        self.sidebar.set_badge(self.IDX_ALERTS, self.page_live.unread_count())
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

    def _set_online(self, ok):
        self.sidebar.set_online(ok)
        self.status_conn.setText("🟢 Connecté au serveur" if ok else "🔴 Hors ligne")

    def _refresh_stats(self):
        try:
            stats = self.api.get_stats()
        except Exception:
            return
        self.page_dashboard.set_stats(stats)
        self.page_stats.set_stats(stats)
        self.page_reports.set_stats(stats)
        # Barre d'état : compteurs + heure de dernière mise à jour.
        from datetime import datetime
        self.status_counts.setText(
            f"🚨 {stats.get('today_count', 0)} aujourd'hui   ·   "
            f"🚔 {stats.get('in_progress_count', 0)} en cours   ·   "
            f"✅ {stats.get('resolved_today', 0)} résolues   ·   "
            f"👮 {stats.get('agents_connected', 0)} agents")
        self.status_updated.setText("Maj " + datetime.now().strftime("%H:%M:%S"))

    # ---- Incident pop-up ----
    def _open_incident(self, alert):
        if alert["id"] in self._open_popups:
            return
        popup = IncidentPopup(alert, self, api_base=API_BASE)
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
        # Ouverture manuelle (double-clic / « Détails ») → l'alerte est « lue ».
        self._mark_alert_read(alert_id)
        alert = self.alerts.get(alert_id)
        if alert:
            self._open_incident(alert)

    def _acknowledge_incident(self, alert):
        """Alerte prise en compte par l'opérateur : son d'accusé de réception."""
        self._mark_alert_read(alert["id"])
        self.alarm.play_ack()
        Toast(self, "✅ Incident pris en compte", "#22c55e").show_for(2500)

    def _mark_alert_read(self, alert_id):
        """Marque une alerte comme lue et rafraîchit la liste + le badge."""
        self.page_live.mark_read(alert_id)
        self.sidebar.set_badge(self.IDX_ALERTS, self.page_live.unread_count())
        self.page_live.set_alerts(self._sorted_alerts())

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
    from PySide6.QtCore import QSettings

    app = QApplication(sys.argv)
    app.setApplicationName("SafeCity")
    app.setWindowIcon(app_icon())
    # Applique le thème mémorisé (clair / sombre) avant de construire l'UI.
    saved_theme = QSettings("SafeCity", "Operateur").value("theme", "dark")
    theme.set_mode(saved_theme if saved_theme in ("light", "dark") else "dark")
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
