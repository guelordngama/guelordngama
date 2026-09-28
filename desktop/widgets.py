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


def _fmt_coords(lat, lng):
    """Coordonnées GPS lisibles : « 11.66470°S, 27.47940°E »."""
    if lat is None or lng is None:
        return "—"
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lng >= 0 else "O"
    return f"{abs(lat):.5f}°{ns}, {abs(lng):.5f}°{ew}"


# --------------------------------------------------------------------------- #
# Fiche d'alerte (format demandé par le centre)
# --------------------------------------------------------------------------- #
TYPE_NAMES = {"vol": "Vol", "braquage": "Braquage", "incendie": "Incendie",
              "accident": "Accident", "violence": "Violence", "agression": "Agression",
              "autre": "Autre"}
STATUS_FICHE = {"active": ("EN ATTENTE", "#ef4444"),
                "assignee": ("PRISE EN CHARGE", "#f97316"),
                "cloturee": ("CLÔTURÉE", "#16a34a")}
_STREET_KINDS = ((("avenue ", "av. ", "av "), "Avenue"), (("rue ",), "Rue"),
                 (("boulevard ", "bd "), "Boulevard"), (("route ",), "Route"),
                 (("chaussée ", "chaussee "), "Chaussée"), (("place ",), "Place"))


def gps_signed(lat, lng):
    """GPS au format décimal signé « -11.664700, 27.479400 » (Google Maps, radio)."""
    if lat is None or lng is None:
        return "—"
    return f"{lat:.6f}, {lng:.6f}"


def street_parts(street):
    """« Avenue Kasai » -> ("Avenue", "Kasai") ; « Rue Mitwaba » -> ("Rue", "Mitwaba")."""
    s = (street or "").strip()
    low = s.lower()
    for prefixes, label in _STREET_KINDS:
        for p in prefixes:
            if low.startswith(p):
                return label, s[len(p):].strip() or s
    return "Avenue / Rue", s


def _geocoding_pending(alert, window_s=45):
    """Adresse encore en recherche (géocodage en arrière-plan juste après l'envoi)."""
    if alert.get("position_approx") or alert.get("street") or alert.get("commune") \
            or alert.get("neighborhood"):
        return False
    from datetime import datetime

    try:
        created = datetime.fromisoformat((alert.get("created_at") or "").replace("Z", ""))
    except ValueError:
        return False
    return (datetime.utcnow() - created).total_seconds() < window_s


def precision_text(alert):
    if alert.get("position_approx"):
        return "⚠️ Position approximative (GPS non obtenu)"
    if alert.get("position_manual"):
        return "Position placée à la main sur la carte"
    acc = alert.get("gps_accuracy_m")
    return f"{round(acc)} m" if acc is not None else "Non communiquée"


def alert_fiche(alert):
    """Lignes de la fiche : liste de (clé, libellé, valeur)."""
    pending = _geocoding_pending(alert)
    unknown = "Recherche en cours…" if pending else "—"
    street_label, street_value = street_parts(alert.get("street"))
    status, _c = STATUS_FICHE.get(alert.get("status"), ((alert.get("status") or "—").upper(), ""))
    return [
        ("type", "Type", TYPE_NAMES.get(alert.get("type"), (alert.get("type") or "—").capitalize())),
        ("citizen", "Citoyen", alert.get("reporter_name") or "Citoyen anonyme"),
        ("phone", "Téléphone", alert.get("reporter_phone") or "Non communiqué"),
        ("commune", "Commune", alert.get("commune") or unknown),
        ("street", street_label, street_value or unknown),
        ("quartier", "Quartier", alert.get("neighborhood") or unknown),
        ("city", "Ville", alert.get("city") or "—"),
        ("gps", "GPS", gps_signed(alert.get("lat"), alert.get("lng"))),
        ("precision", "Précision", precision_text(alert)),
        ("time", "Heure", alert.get("time") or "—"),
        ("status", "Statut", status),
    ]


def alert_fiche_text(alert):
    """Fiche texte à copier-coller (WhatsApp, SMS, radio)."""
    head = {"active": "🔴 NOUVELLE ALERTE", "assignee": "🟠 ALERTE PRISE EN CHARGE",
            "cloturee": "🟢 ALERTE CLÔTURÉE"}.get(alert.get("status"), "🔴 ALERTE")
    lines = [head + (f"  #{alert['reference']}" if alert.get("reference") else ""), ""]
    for key, label, value in alert_fiche(alert):
        if key == "gps":
            lines.append("")
        lines.append(f"{label} : {value}")
    if alert.get("lat") is not None:
        lines.append(f"Carte : https://www.google.com/maps?q={alert['lat']:.6f},{alert['lng']:.6f}")
    return "\n".join(lines)


def _shadow(widget, blur=22, alpha=None):
    """Ombre douce sous les cartes (plus légère en thème clair)."""
    if alpha is None:
        alpha = 22 if theme.current_mode() == "light" else 90
    else:
        alpha = min(alpha, 26) if theme.current_mode() == "light" else alpha
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(4)
    eff.setColor(QColor(16, 24, 40, alpha))
    widget.setGraphicsEffect(eff)


class StatCard(QFrame):
    """Tuile de statistique : icône, grande valeur, libellé, accent coloré.

    Optionnellement cliquable (émet ``clicked``) et pourvue d'un sous-titre
    contextuel (``set_subtitle``).
    """

    clicked = Signal()

    def __init__(self, icon, label, color=theme.ACCENT, filled=False):
        super().__init__()
        self.setObjectName("statFilled" if filled else "card")
        self.setMinimumHeight(110)
        self._color = color
        self._clickable = False
        self._filled = filled
        _shadow(self)
        if filled:
            # Tuile pleine (maquette) : dégradé de la couleur, texte blanc.
            dark = QColor(color).darker(128).name()
            self.setStyleSheet(
                f"QFrame#statFilled {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                f" stop:0 {color}, stop:1 {dark}); border: none; border-radius: 16px; }}"
                f"QFrame#statFilled QLabel {{ color: white; background: transparent; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        chip = QLabel(icon)
        chip.setAlignment(Qt.AlignCenter)
        chip.setFixedSize(52, 52)
        chip.setStyleSheet(
            f"background: {'rgba(255,255,255,0.20)' if filled else theme.tint(color, 0.14)};"
            " border-radius: 14px; font-size: 24px;"
        )
        lay.addWidget(chip)

        col = QVBoxLayout()
        col.setSpacing(2)
        self.value = QLabel("0")
        self.value.setObjectName("cardValue")
        self.value.setStyleSheet(f"color: {'white' if filled else color};")
        lbl = QLabel(label)
        lbl.setObjectName("cardLabel")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        self.subtitle.setStyleSheet(
            "font-size: 11px;" + (" color: rgba(255,255,255,0.85);" if filled else ""))
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
            f"background: {theme.tint(color, 0.15)}; color: {color}; border-radius: 12px;"
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
        self.title_label = QLabel(self._title_text(alert))
        self.title_label.setStyleSheet("color: white; font-size: 22px; font-weight: 800;")
        title = self.title_label
        ref = alert.get("reference")
        sub = QLabel((f"#{ref}  ·  " if ref else "")
                     + f"{TYPE_NAMES.get(alert.get('type'), (alert.get('type') or '').capitalize())}"
                     + f"  ·  Urgence : {theme.urgency_label(alert.get('urgency'))}")
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
            f"background: {theme.tint(color, 0.14)}; color: {color}; font-weight: 800; "
            f"padding: 7px; font-size: 13px;")
        root.addWidget(self.timer_label)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_timer.start(1000)
        self._tick_elapsed()

        # Bandeau « position approximative » : le GPS du citoyen n'a pas été
        # obtenu → la position n'est PAS fiable, la patrouille doit rappeler.
        if alert.get("position_approx"):
            warn = QLabel("⚠️  Position approximative — GPS du citoyen non obtenu. "
                          "Rappelez le citoyen pour confirmer le lieu.")
            warn.setAlignment(Qt.AlignCenter)
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f"background: {theme.tint('#f59e0b', 0.16)}; color: #b45309; font-weight: 800; "
                "padding: 8px; font-size: 13px;")
            root.addWidget(warn)

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
                f"background: {theme.tint(theme.ACCENT, 0.14)}; color: {theme.ACCENT}; "
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
        self._coords_text = gps_signed(alert.get("lat"), alert.get("lng"))
        # Fiche d'alerte, dans l'ordre demandé par le centre (mise à jour en
        # direct quand l'adresse arrive du géocodage).
        self._fiche_keys = {}
        self._fiche_values = {}
        rows = alert_fiche(alert) + [
            ("distance", "Distance équipe",
             f"{round(alert['distance_m'])} m" if alert.get("distance_m") is not None else "—")]
        for i, (key, label, value) in enumerate(rows):
            kl = QLabel(label + " :")
            kl.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
            vl = QLabel(str(value))
            vl.setWordWrap(True)
            vl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            vl.setStyleSheet(self._value_style(key, alert))
            info.addWidget(kl, i, 0, Qt.AlignTop)
            info.addWidget(vl, i, 1, Qt.AlignLeft if key == "status" else Qt.Alignment())
            self._fiche_keys[key] = kl
            self._fiche_values[key] = vl
        content.addLayout(info, 1)

        self._photo_pixmap = None
        if alert.get("photo_url"):
            self.photo_label = QLabel("📷\nChargement…")
            self.photo_label.setFixedSize(190, 140)
            self.photo_label.setAlignment(Qt.AlignCenter)
            self.photo_label.setCursor(Qt.PointingHandCursor)
            self.photo_label.setToolTip("Cliquer pour agrandir")
            self.photo_label.setStyleSheet(
                f"background: {theme.PANEL}; border: 1px solid {theme.BORDER}; "
                f"border-radius: 10px; color: {theme.MUTED};")
            # Clic sur la miniature → photo en grand.
            self.photo_label.mousePressEvent = lambda _e: self._open_full_photo()
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

        # Copier la position GPS exacte (pour la transmettre à une patrouille).
        copy_row = QHBoxLayout()
        copy_row.setSpacing(8)
        self.btn_copy_fiche = QPushButton("📋  Copier la fiche")
        self.btn_copy_fiche.setObjectName("ghost")
        self.btn_copy_fiche.setCursor(Qt.PointingHandCursor)
        self.btn_copy_fiche.setToolTip("Copie toute la fiche (à coller dans WhatsApp, SMS…)")
        self.btn_copy_fiche.clicked.connect(self._copy_fiche)
        copy_row.addWidget(self.btn_copy_fiche)
        if self._coords_text != "—":
            self.btn_copy_gps = QPushButton("📍  Copier le GPS")
            self.btn_copy_gps.setObjectName("ghost")
            self.btn_copy_gps.setCursor(Qt.PointingHandCursor)
            self.btn_copy_gps.setToolTip(self._coords_text)
            self.btn_copy_gps.clicked.connect(self._copy_coords)
            copy_row.addWidget(self.btn_copy_gps)
        body.addLayout(copy_row)

        # Message vocal joint par le citoyen : lecteur intégré (en urgence,
        # l'opérateur doit pouvoir l'écouter tout de suite).
        self._player = None
        self._audio_out = None
        audio_rel = alert.get("audio_url")
        if audio_rel:
            self._audio_url = (self.api_base + audio_rel
                               if audio_rel.startswith("/") else audio_rel)
            self.btn_voice = QPushButton("🎧  Écouter le message vocal du citoyen")
            self.btn_voice.setObjectName("warn")
            self.btn_voice.setMinimumHeight(42)
            self.btn_voice.setCursor(Qt.PointingHandCursor)
            self.btn_voice.clicked.connect(self._toggle_voice)
            body.addWidget(self.btn_voice)

        # Vidéo jointe par le citoyen : lecteur intégré (fenêtre dédiée).
        video_rel = alert.get("video_url")
        if video_rel:
            self._video_url = (self.api_base + video_rel
                               if video_rel.startswith("/") else video_rel)
            self.btn_video = QPushButton("🎬  Voir la vidéo du citoyen")
            self.btn_video.setObjectName("warn")
            self.btn_video.setMinimumHeight(42)
            self.btn_video.setCursor(Qt.PointingHandCursor)
            self.btn_video.clicked.connect(self._open_citizen_video)
            body.addWidget(self.btn_video)

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
                        self._photo_pixmap = pix  # conservée pour l'agrandissement
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

    def _copy_coords(self):
        """Copie la position GPS exacte dans le presse-papiers."""
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._coords_text)
        self.btn_copy_gps.setText("✓  GPS copié")
        QTimer.singleShot(1800, lambda: self.btn_copy_gps.setText("📍  Copier le GPS"))

    def _copy_fiche(self):
        """Copie la fiche complète de l'alerte (texte prêt à partager)."""
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(alert_fiche_text(self.alert))
        self.btn_copy_fiche.setText("✓  Fiche copiée")
        QTimer.singleShot(1800, lambda: self.btn_copy_fiche.setText("📋  Copier la fiche"))

    # ---- Fiche : style et mise à jour en direct ----
    @staticmethod
    def _title_text(alert):
        return {"active": "🔴  NOUVELLE ALERTE", "assignee": "🟠  ALERTE PRISE EN CHARGE",
                "cloturee": "🟢  ALERTE CLÔTURÉE"}.get(alert.get("status"), "🔴  ALERTE")

    @staticmethod
    def _value_style(key, alert):
        if key == "status":
            color = STATUS_FICHE.get(alert.get("status"), ("", theme.TEXT))[1] or theme.TEXT
            return (f"font-weight: 800; color: {color}; background: {theme.tint(color, 0.12)};"
                    " border-radius: 8px; padding: 2px 8px;")
        if key in ("commune", "street", "quartier") and _geocoding_pending(alert):
            return f"font-weight: 600; color: {theme.MUTED}; font-style: italic;"
        if key == "precision" and (alert.get("position_approx")):
            return "font-weight: 800; color: #b45309;"
        if key == "gps":
            return "font-weight: 800; font-family: Consolas, 'DejaVu Sans Mono', monospace;"
        return "font-weight: 700;"

    def update_alert(self, alert):
        """L'alerte a changé (adresse géocodée, prise en charge…) : on rafraîchit
        la fiche sans refermer la fenêtre."""
        self.alert = alert
        self.title_label.setText(self._title_text(alert))
        for key, label, value in alert_fiche(alert):
            vl = self._fiche_values.get(key)
            if vl is None:
                continue
            vl.setText(str(value))
            vl.setStyleSheet(self._value_style(key, alert))
            if key == "street":
                self._fiche_keys[key].setText(label + " :")

    def _open_full_photo(self):
        """Affiche la photo du citoyen en grand dans une fenêtre."""
        if self._photo_pixmap is None or self._photo_pixmap.isNull():
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel as _QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle("📷 Photo du citoyen")
        dlg.setStyleSheet(theme.QSS + f"QDialog {{ background: {theme.BG}; }}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(10, 10, 10, 10)
        lbl = _QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setPixmap(self._photo_pixmap.scaled(
            820, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(lbl)
        dlg.exec()

    # ---- Lecture du message vocal joint à l'alerte ----
    def _toggle_voice(self):
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception:
            self.btn_voice.setText("🔊 Lecture audio non disponible sur ce poste")
            self.btn_voice.setEnabled(False)
            return

        if self._player is None:
            self._audio_out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_out)
            self._player.playbackStateChanged.connect(self._on_voice_state)
            self._player.errorOccurred.connect(self._on_voice_error)

        # Clic pendant la lecture → arrêt.
        if self._player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self._player.stop()
            self._reset_voice_btn()
            return

        self._audio_out.setVolume(1.0)
        self._player.setSource(QUrl(self._audio_url))
        self._player.play()
        self.btn_voice.setText("⏹  Arrêter le message vocal")

    def _reset_voice_btn(self):
        if hasattr(self, "btn_voice"):
            self.btn_voice.setText("🎧  Écouter le message vocal du citoyen")

    def _on_voice_state(self, state):
        from PySide6.QtMultimedia import QMediaPlayer

        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._reset_voice_btn()

    def _on_voice_error(self, *_a):
        if hasattr(self, "btn_voice"):
            self.btn_voice.setText("🔊 Impossible de lire ce vocal (réseau ou format)")

    # ---- Lecture de la vidéo jointe à l'alerte ----
    def _open_citizen_video(self):
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget
            from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout
        except Exception:
            self._open_video_external()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("🎬 Vidéo du citoyen")
        dlg.resize(760, 520)
        dlg.setStyleSheet(theme.QSS + f"QDialog {{ background: {theme.BG}; }}")
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
        player.setSource(QUrl(self._video_url))
        player.play()

        def toggle():
            if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.pause(); b_play.setText("▶  Lire")
            else:
                player.play(); b_play.setText("⏸  Pause")

        b_play.clicked.connect(toggle)
        b_ext.clicked.connect(self._open_video_external)
        dlg.finished.connect(lambda _=0: player.stop())
        dlg.exec()

    def _open_video_external(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl(self._video_url))


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
