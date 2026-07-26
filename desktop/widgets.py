"""Composants d'interface réutilisables du poste opérateur SafeCity."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import theme


def _shadow(widget, blur=24, alpha=90):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(6)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


class StatCard(QFrame):
    """Tuile de statistique : icône, grande valeur, libellé, accent coloré.

    Optionnellement cliquable (émet ``clicked``) et pourvue d'un sous-titre
    contextuel (``set_subtitle``).
    """

    clicked = Signal()

    def __init__(self, icon, label, color=theme.ACCENT):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(110)
        self._color = color
        self._clickable = False
        _shadow(self)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        chip = QLabel(icon)
        chip.setAlignment(Qt.AlignCenter)
        chip.setFixedSize(52, 52)
        chip.setStyleSheet(
            f"background: {color}22; border-radius: 14px; font-size: 24px;"
        )
        lay.addWidget(chip)

        col = QVBoxLayout()
        col.setSpacing(2)
        self.value = QLabel("0")
        self.value.setObjectName("cardValue")
        self.value.setStyleSheet(f"color: {color};")
        lbl = QLabel(label)
        lbl.setObjectName("cardLabel")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        self.subtitle.setStyleSheet("font-size: 11px;")
        self.subtitle.hide()
        col.addStretch()
        col.addWidget(self.value)
        col.addWidget(lbl)
        col.addWidget(self.subtitle)
        col.addStretch()
        lay.addLayout(col)
        lay.addStretch()

    def set_value(self, v):
        self.value.setText(str(v))

    def set_subtitle(self, text):
        """Affiche (ou masque) une ligne d'information contextuelle."""
        if text:
            self.subtitle.setText(str(text))
            self.subtitle.show()
        else:
            self.subtitle.clear()
            self.subtitle.hide()

    def set_clickable(self, on=True):
        """Rend la tuile interactive (curseur main + émission de ``clicked``)."""
        self._clickable = on
        self.setCursor(Qt.PointingHandCursor if on else Qt.ArrowCursor)

    def mousePressEvent(self, event):  # noqa: N802 (API Qt)
        if self._clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class Card(QFrame):
    """Panneau générique avec titre."""

    def __init__(self, title=None):
        super().__init__()
        self.setObjectName("card")
        _shadow(self, blur=20, alpha=70)
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(18, 16, 18, 18)
        self.v.setSpacing(12)
        if title:
            t = QLabel(title)
            t.setObjectName("sectionTitle")
            self.v.addWidget(t)

    def add(self, w):
        self.v.addWidget(w)

    def add_layout(self, layout):
        self.v.addLayout(layout)


class Badge(QLabel):
    """Petite étiquette colorée (urgence, statut)."""

    def __init__(self, text, color):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(24)
        self.setStyleSheet(
            f"background: {color}26; color: {color}; border-radius: 12px;"
            f"padding: 0 12px; font-weight: 700; font-size: 12px;"
        )


class Toast(QFrame):
    """Notification visuelle éphémère en superposition (coin haut-droit)."""

    def __init__(self, parent, text, color=theme.ACCENT):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {theme.PANEL}; border: 1px solid {color}; border-radius: 12px;"
        )
        _shadow(self, blur=30, alpha=120)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 600;")
        lay.addWidget(dot)
        lay.addWidget(lbl)
        self.adjustSize()

    def show_for(self, ms=4000):
        self.show()
        self.raise_()
        QTimer.singleShot(ms, self.close)


class IncidentPopup(QDialog):
    """Fenêtre d'incident qui s'ouvre à l'arrivée d'une alerte.

    Affiche citoyen, téléphone, heure, GPS, urgence, média, et propose les
    actions : Accepter, Envoyer une patrouille, Appeler, Ouvrir la carte,
    Clôturer.
    """

    accept_incident = Signal(dict)
    send_patrol = Signal(dict)
    assign_agent = Signal(dict)
    open_on_map = Signal(dict)
    close_incident = Signal(dict)

    def __init__(self, alert, parent=None, api_base=""):
        super().__init__(parent)
        self.alert = alert
        self.api_base = (api_base or "").rstrip("/")
        self.setWindowTitle("🚨 Nouvelle alerte")
        self.setMinimumWidth(520)
        self.setStyleSheet(theme.QSS + f"QDialog {{ background: {theme.BG}; }}")

        color = theme.urgency_color(alert.get("urgency"))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Bandeau supérieur coloré selon l'urgence (+ heure de réception).
        header = QFrame()
        header.setStyleSheet(f"background: {color};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 16)
        htext = QVBoxLayout()
        htext.setSpacing(2)
        title = QLabel(f"🚨  {(alert.get('type') or '').upper()}")
        title.setStyleSheet("color: white; font-size: 22px; font-weight: 800;")
        sub = QLabel(f"Niveau d'urgence : {theme.urgency_label(alert.get('urgency'))}")
        sub.setStyleSheet("color: rgba(255,255,255,0.92); font-weight: 600;")
        htext.addWidget(title)
        htext.addWidget(sub)
        hl.addLayout(htext)
        hl.addStretch()
        recv = QLabel(f"Reçue à\n{alert.get('time') or '—'}")
        recv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        recv.setStyleSheet("color: rgba(255,255,255,0.95); font-weight: 800; font-size: 15px;")
        hl.addWidget(recv)
        root.addWidget(header)

        # Minuteur « reçue il y a … » (sensibilise au temps de réponse).
        self.timer_label = QLabel("")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet(
            f"background: {color}22; color: {color}; font-weight: 800; "
            f"padding: 7px; font-size: 13px;")
        root.addWidget(self.timer_label)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_timer.start(1000)
        self._tick_elapsed()

        # Bandeau « signalements liés » : plusieurs citoyens ont signalé le même
        # incident → une seule intervention suffit.
        dup = alert.get("duplicate_count") or 0
        if dup > 0:
            total = dup + 1
            banner = QLabel(f"🔁  {total} signalements du même incident "
                            f"(regroupés) — une seule intervention nécessaire")
            banner.setAlignment(Qt.AlignCenter)
            banner.setWordWrap(True)
            banner.setStyleSheet(
                f"background: {theme.ACCENT}22; color: {theme.ACCENT}; "
                f"font-weight: 800; padding: 8px; font-size: 13px;")
            root.addWidget(banner)

        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 20)
        body.setSpacing(12)

        # Infos (gauche) + miniature photo (droite).
        content = QHBoxLayout()
        content.setSpacing(16)
        info = QGridLayout()
        info.setVerticalSpacing(8)
        info.setHorizontalSpacing(14)
        rows = [
            ("👤 Citoyen", alert.get("reporter_name") or "Citoyen anonyme"),
            ("📞 Téléphone", alert.get("reporter_phone") or "Non communiqué"),
            ("🕒 Heure", alert.get("time") or "—"),
            ("📍 Quartier", alert.get("neighborhood") or "—"),
            ("🌐 Position", f"{alert.get('lat'):.5f}, {alert.get('lng'):.5f}"),
            ("📏 Distance équipe", f"{round(alert['distance_m'])} m" if alert.get("distance_m") is not None else "—"),
        ]
        for i, (k, v) in enumerate(rows):
            kl = QLabel(k)
            kl.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
            vl = QLabel(str(v))
            vl.setWordWrap(True)
            vl.setStyleSheet("font-weight: 700;")
            info.addWidget(kl, i, 0, Qt.AlignTop)
            info.addWidget(vl, i, 1)
        content.addLayout(info, 1)

        if alert.get("photo_url"):
            self.photo_label = QLabel("📷\nChargement…")
            self.photo_label.setFixedSize(190, 140)
            self.photo_label.setAlignment(Qt.AlignCenter)
            self.photo_label.setStyleSheet(
                f"background: {theme.PANEL}; border: 1px solid {theme.BORDER}; "
                f"border-radius: 10px; color: {theme.MUTED};")
            content.addWidget(self.photo_label, 0, Qt.AlignTop)
            self._load_photo(alert["photo_url"])
        body.addLayout(content)

        # Description (pleine largeur).
        if alert.get("description"):
            desc = QLabel("📝  " + alert["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"background: {theme.PANEL}; border: 1px solid {theme.BORDER}; "
                f"border-radius: 10px; padding: 10px 12px; font-weight: 600;")
            body.addWidget(desc)

        # Boutons d'action — « Accepter » mis en avant sur toute la largeur.
        b_accept = QPushButton("✅  Accepter l'intervention")
        b_accept.setObjectName("success")
        b_accept.setMinimumHeight(42)
        body.addWidget(b_accept)

        actions = QGridLayout()
        actions.setSpacing(8)
        b_patrol = QPushButton("🚔 Envoyer une patrouille")
        b_patrol.setObjectName("warn")
        b_agent = QPushButton("👮 Affecter un agent")
        b_agent.setObjectName("warn")
        b_call = QPushButton("📞 Appeler")
        b_call.setObjectName("ghost")
        b_map = QPushButton("🗺️ Ouvrir la carte")
        b_map.setObjectName("ghost")
        b_close = QPushButton("🏁 Clôturer l'incident")
        b_close.setObjectName("danger")
        actions.addWidget(b_patrol, 0, 0)
        actions.addWidget(b_agent, 0, 1)
        actions.addWidget(b_call, 1, 0)
        actions.addWidget(b_map, 1, 1)
        actions.addWidget(b_close, 2, 0, 1, 2)
        body.addLayout(actions)
        root.addLayout(body)

        b_accept.clicked.connect(lambda: (self.accept_incident.emit(self.alert), self.accept()))
        b_patrol.clicked.connect(lambda: self.send_patrol.emit(self.alert))
        b_agent.clicked.connect(lambda: (self.assign_agent.emit(self.alert), self.accept()))
        b_call.clicked.connect(self._call)
        b_map.clicked.connect(lambda: (self.open_on_map.emit(self.alert), self.accept()))
        b_close.clicked.connect(lambda: (self.close_incident.emit(self.alert), self.accept()))

    def _tick_elapsed(self):
        from datetime import datetime

        created = self.alert.get("created_at")
        text = "⏱  Intervention en attente"
        try:
            if created:
                dt = datetime.fromisoformat(created.replace("Z", ""))
                secs = max(0, int((datetime.utcnow() - dt).total_seconds()))
                h, rem = divmod(secs, 3600)
                m, s = divmod(rem, 60)
                hms = (f"{h:02d}:" if h else "") + f"{m:02d}:{s:02d}"
                text = f"⏱  Reçue il y a {hms} — délai de réponse en cours"
        except Exception:
            pass
        self.timer_label.setText(text)

    def _load_photo(self, rel_url):
        """Charge la miniature de la photo en arrière-plan (non bloquant)."""
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QPixmap
            from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

            url = self.api_base + rel_url if rel_url.startswith("/") else rel_url
            self._nam = QNetworkAccessManager(self)
            reply = self._nam.get(QNetworkRequest(QUrl(url)))

            def done():
                try:
                    pix = QPixmap()
                    pix.loadFromData(bytes(reply.readAll().data()))
                    if not pix.isNull():
                        self.photo_label.setPixmap(pix.scaled(
                            190, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    else:
                        self.photo_label.setText("📷 Photo\n(voir le détail)")
                except Exception:
                    self.photo_label.setText("📷 Photo jointe")
                reply.deleteLater()

            reply.finished.connect(done)
        except Exception:
            self.photo_label.setText("📷 Photo jointe")

    def _call(self):
        from PySide6.QtWidgets import QMessageBox

        phone = self.alert.get("reporter_phone") or "non communiqué"
        QMessageBox.information(self, "Appel", f"Appel du citoyen : {phone}")


class AgentDialog(QDialog):
    """Formulaire de création / modification d'un agent."""

    ROLES = [("Agent", "agent"), ("Opérateur", "operator"),
             ("Superviseur", "supervisor"), ("Administrateur", "admin")]

    def __init__(self, agent=None, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.setStyleSheet(theme.QSS)
        self.setMinimumWidth(400)
        self.setWindowTitle("Modifier l'agent" if agent else "Ajouter un agent")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(6)
        title = QLabel("✏️ Modifier l'agent" if agent else "➕ Nouvel agent")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self.name = QLineEdit(agent.get("name", "") if agent else "")
        self.email = QLineEdit(agent.get("email", "") if agent else "")
        self.phone = QLineEdit(agent.get("phone", "") if agent else "")
        self.role = QComboBox()
        for label, value in self.ROLES:
            self.role.addItem(label, value)
        if agent:
            idx = self.role.findData(agent.get("role", "agent"))
            self.role.setCurrentIndex(max(0, idx))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText(
            "Laisser vide pour ne pas changer" if agent else "Min. 6 caractères")
        self.active = QCheckBox("Compte actif")
        self.active.setChecked(agent.get("active", True) if agent else True)

        form.addRow("Nom", self.name)
        form.addRow("Email", self.email)
        form.addRow("Téléphone", self.phone)
        form.addRow("Rôle", self.role)
        form.addRow("Mot de passe", self.password)
        form.addRow("", self.active)
        root.addLayout(form)

        self.error = QLabel("")
        self.error.setStyleSheet("color: #ff8181;")
        self.error.setWordWrap(True)
        root.addWidget(self.error)

        btns = QHBoxLayout()
        cancel = QPushButton("Annuler")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Enregistrer")
        ok.clicked.connect(self._validate)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(ok)
        root.addLayout(btns)

    def _validate(self):
        if not self.name.text().strip():
            return self._err("Le nom est requis.")
        if "@" not in self.email.text():
            return self._err("Email invalide.")
        pwd = self.password.text()
        if not self.agent and len(pwd) < 6:
            return self._err("Mot de passe requis (min. 6 caractères).")
        if pwd and len(pwd) < 6:
            return self._err("Mot de passe trop court (min. 6).")
        self.accept()

    def _err(self, msg):
        self.error.setText(msg)

    def payload(self):
        data = {
            "name": self.name.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
            "role": self.role.currentData(),
            "active": self.active.isChecked(),
        }
        if self.password.text():
            data["password"] = self.password.text()
        return data
