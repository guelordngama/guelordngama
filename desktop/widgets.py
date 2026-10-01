"""Composants d'interface réutilisables du poste opérateur SafeCity."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import theme


def _circular_pixmap(pix, size):
    """Recadre et masque un QPixmap en cercle (pour les photos de profil).

    border-radius en QSS ne découpe pas un QPixmap posé sur un QLabel : il faut
    dessiner le découpage nous-mêmes.
    """
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter, QPainterPath, QPixmap

    scaled = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    scaled = scaled.copy(x, y, size, size)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, size, size))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return out


def _avatar_initials(name):
    """Initiales pour l'avatar par défaut (pas de photo) : « Jean Kabila » -> JK."""
    parts = [w for w in (name or "").split() if w]
    if not parts:
        return "?"
    first = parts[0][0]
    second = parts[1][0] if len(parts) > 1 else ""
    return (first + second).upper()


def start_avatar_load(owner, label, api_base, avatar_url, size):
    """Charge une photo de profil en arrière-plan et la recadre en cercle sur un
    QLabel qui affiche déjà les initiales par défaut. `owner` doit garder une
    référence (le gestionnaire réseau) vivante le temps de la requête."""
    if not avatar_url:
        return
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QPixmap
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

        url = api_base + avatar_url if avatar_url.startswith("/") else avatar_url
        owner._avatar_nam = QNetworkAccessManager(owner)
        reply = owner._avatar_nam.get(QNetworkRequest(QUrl(url)))

        def done():
            try:
                pix = QPixmap()
                pix.loadFromData(bytes(reply.readAll().data()))
                if not pix.isNull():
                    label.setPixmap(_circular_pixmap(pix, size))
                    label.setText("")
            except Exception:
                pass
            reply.deleteLater()

        reply.finished.connect(done)
    except Exception:
        pass


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
                "assignee": ("EN COURS", "#f97316"),
                "cloturee": ("TRAITÉ", "#16a34a")}
FALSE_ALARM_FICHE = ("FAUSSE ALERTE", "#64748b")


def fiche_status(alert):
    """(libellé, couleur) du statut affiché dans la fiche."""
    if alert.get("false_alarm"):
        return FALSE_ALARM_FICHE
    return STATUS_FICHE.get(alert.get("status"),
                            ((alert.get("status") or "—").upper(), theme.TEXT))


AGENT_STATUS = {"available": "Disponible", "busy": "En intervention", "offline": "Hors service"}


def incident_ref(alert):
    """« SC-2026-0048 » (n° d'intervention) ; repli sur le code de suivi."""
    return alert.get("incident_number") or alert.get("reference") or f"{alert.get('id', '')}"


def _haversine_m(a_lat, a_lng, b_lat, b_lng):
    import math

    r = 6371000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = math.radians(b_lat - a_lat), math.radians(b_lng - a_lng)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(x)))


def _ago(iso):
    from datetime import datetime

    try:
        dt = datetime.fromisoformat((iso or "").replace("Z", ""))
    except ValueError:
        return ""
    m = int((datetime.utcnow() - dt).total_seconds() // 60)
    return "à l'instant" if m < 1 else f"il y a {m} min" if m < 60 else f"il y a {m // 60} h"


def assignment_parts(alert):
    """(ligne agent, position, statut) pour « Agent X → Intervention #… »."""
    ag = alert.get("assigned_agent") or {}
    if not ag:
        return "Non affecté", "—", "—"
    line = f"{ag.get('name') or 'Agent'} → Intervention #{incident_ref(alert)}"
    if ag.get("lat") is not None and ag.get("lng") is not None:
        pos = gps_signed(ag["lat"], ag["lng"])
        extra = []
        if alert.get("lat") is not None:
            d = _haversine_m(ag["lat"], ag["lng"], alert["lat"], alert["lng"])
            extra.append(f"à {d / 1000:.1f} km".replace(".", ",") if d >= 1000 else f"à {round(d)} m")
            extra.append(f"≈ {max(1, round(d * 1.3 / 1000 / 25 * 60))} min en moto")
        if ag.get("last_seen"):
            extra.append(_ago(ag["last_seen"]))
        pos += "  (" + " · ".join(x for x in extra if x) + ")" if extra else ""
    else:
        pos = "Position inconnue (portail non connecté)"
    return line, pos, AGENT_STATUS.get(ag.get("availability"), ag.get("availability") or "—")
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
    status, _c = fiche_status(alert)
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
    ] + list(zip(("agent", "agent_pos", "agent_status"),
                 ("Agent", "Position agent", "Statut agent"), assignment_parts(alert)))


def alert_fiche_text(alert):
    """Fiche texte à copier-coller (WhatsApp, SMS, radio)."""
    head = {"active": "🔴 NOUVELLE ALERTE", "assignee": "🟠 INTERVENTION EN COURS",
            "cloturee": "🟢 INTERVENTION TRAITÉE"}.get(alert.get("status"), "🔴 ALERTE")
    lines = [head + f"  #{incident_ref(alert)}", ""]
    for key, label, value in alert_fiche(alert):
        if key in ("gps", "agent"):
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
    false_alarm = Signal(dict)
    show_journal = Signal(dict)

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
        sub = QLabel(f"#{incident_ref(alert)}  ·  "
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

        # Zone défilante pour tout ce qui suit : sur un petit écran, la fiche
        # (photo, description, boutons) ne tenait pas entièrement et les derniers
        # boutons (Fausse alerte, Journal, Clôturer) devenaient inaccessibles.
        # Le bandeau du haut, lui, reste toujours visible.
        scroll = QScrollArea()
        scroll.setObjectName("popupScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea#popupScroll { background: transparent; border: none; }")
        scroll_host = QWidget()
        scroll_host.setStyleSheet(f"background: {theme.BG};")
        col = QVBoxLayout(scroll_host)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        scroll.setWidget(scroll_host)

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
            col.addWidget(warn)

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
            col.addWidget(banner)

        # Traçabilité : fausse alerte déjà qualifiée / citoyen déjà signalé.
        self.false_banner = QLabel("")
        self.false_banner.setAlignment(Qt.AlignCenter)
        self.false_banner.setWordWrap(True)
        self.false_banner.setStyleSheet(
            f"background: {theme.tint('#64748b', 0.16)}; color: #475569; font-weight: 800; "
            "padding: 8px; font-size: 13px;")
        col.addWidget(self.false_banner)
        self.reporter_banner = QLabel("")
        self.reporter_banner.setAlignment(Qt.AlignCenter)
        self.reporter_banner.setWordWrap(True)
        self.reporter_banner.setStyleSheet(
            f"background: {theme.tint('#f59e0b', 0.16)}; color: #b45309; font-weight: 700; "
            "padding: 8px; font-size: 12px;")
        col.addWidget(self.reporter_banner)
        self._refresh_trace_banners(alert)

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
        self.btn_false = QPushButton("🚫 Fausse alerte")
        self.btn_false.setObjectName("ghost")
        self.btn_false.setToolTip("Classer en fausse alerte (motif obligatoire, action tracée)")
        b_journal = QPushButton("📜 Journal de l'intervention")
        b_journal.setObjectName("ghost")
        b_journal.setToolTip("Qui a fait quoi, et quand, sur cet incident")
        actions.addWidget(b_patrol, 0, 0)
        actions.addWidget(b_agent, 0, 1)
        actions.addWidget(b_call, 1, 0)
        actions.addWidget(b_map, 1, 1)
        actions.addWidget(self.btn_false, 2, 0)
        actions.addWidget(b_journal, 2, 1)
        actions.addWidget(b_close, 3, 0, 1, 2)
        self.btn_false.setEnabled(not alert.get("false_alarm"))
        body.addLayout(actions)
        col.addLayout(body)

        root.addWidget(scroll, 1)

        # Ne jamais dépasser la hauteur utile de l'écran (sinon les boutons du
        # bas sortent de l'écran, sans zone défilante pour les atteindre).
        screen = QApplication.primaryScreen()
        max_h = max(460, screen.availableGeometry().height() - 60) if screen else 900
        self.setMaximumHeight(max_h)
        # Une QScrollArea ne propage pas la hauteur de son contenu à la fenêtre
        # (son sizeHint par défaut est petit) : sans ce calcul, la fenêtre
        # s'ouvrait trop petite, avec un défilement même là où tout tenait.
        # On vise donc la hauteur réelle du contenu, plafonnée à l'écran.
        target_h = (header.sizeHint().height() + self.timer_label.sizeHint().height()
                    + scroll_host.sizeHint().height() + 24)
        self.resize(max(self.minimumWidth(), 560), min(target_h, max_h))

        b_accept.clicked.connect(lambda: (self.accept_incident.emit(self.alert), self.accept()))
        b_patrol.clicked.connect(lambda: self.send_patrol.emit(self.alert))
        b_agent.clicked.connect(lambda: (self.assign_agent.emit(self.alert), self.accept()))
        b_call.clicked.connect(self._call)
        b_map.clicked.connect(lambda: (self.open_on_map.emit(self.alert), self.accept()))
        b_close.clicked.connect(lambda: (self.close_incident.emit(self.alert), self.accept()))
        self.btn_false.clicked.connect(lambda: self.false_alarm.emit(self.alert))
        b_journal.clicked.connect(lambda: self.show_journal.emit(self.alert))

    def _refresh_trace_banners(self, alert):
        if alert.get("false_alarm"):
            self.false_banner.setText(
                f"🚫  Classée FAUSSE ALERTE par {alert.get('false_alarm_by') or '—'} — "
                f"motif : {alert.get('false_alarm_reason') or '—'}")
        self.false_banner.setVisible(bool(alert.get("false_alarm")))
        n = alert.get("reporter_false_alarms") or 0
        if n and not alert.get("false_alarm"):
            self.reporter_banner.setText(
                f"⚠️  Ce citoyen a déjà {n} "
                + ("fausses alertes enregistrées" if n > 1 else "fausse alerte enregistrée")
                + ". Vérifiez — mais traitez l'alerte : une vraie urgence reste possible.")
        self.reporter_banner.setVisible(bool(n) and not alert.get("false_alarm"))

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
        if alert.get("false_alarm"):
            return "⚪  FAUSSE ALERTE"
        return {"active": "🔴  NOUVELLE ALERTE", "assignee": "🟠  INTERVENTION EN COURS",
                "cloturee": "🟢  INTERVENTION TRAITÉE"}.get(alert.get("status"), "🔴  ALERTE")

    @staticmethod
    def _value_style(key, alert):
        if key == "status":
            color = fiche_status(alert)[1] or theme.TEXT
            return (f"font-weight: 800; color: {color}; background: {theme.tint(color, 0.12)};"
                    " border-radius: 8px; padding: 2px 8px;")
        if key in ("commune", "street", "quartier") and _geocoding_pending(alert):
            return f"font-weight: 600; color: {theme.MUTED}; font-style: italic;"
        if key == "precision" and (alert.get("position_approx")):
            return "font-weight: 800; color: #b45309;"
        if key == "gps":
            return "font-weight: 800; font-family: Consolas, 'DejaVu Sans Mono', monospace;"
        if key == "agent" and alert.get("assigned_agent"):
            return f"font-weight: 800; color: {theme.ACCENT};"
        if key == "agent_status" and alert.get("assigned_agent"):
            avail = (alert.get("assigned_agent") or {}).get("availability")
            return f"font-weight: 800; color: {'#16a34a' if avail == 'available' else '#f97316'};"
        return "font-weight: 700;"

    def update_alert(self, alert):
        """L'alerte a changé (adresse géocodée, prise en charge…) : on rafraîchit
        la fiche sans refermer la fenêtre."""
        self.alert = alert
        self.title_label.setText(self._title_text(alert))
        self._refresh_trace_banners(alert)
        self.btn_false.setEnabled(not alert.get("false_alarm"))
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

    def __init__(self, agent=None, parent=None, api_base=""):
        super().__init__(parent)
        self.agent = agent
        self.api_base = (api_base or "").rstrip("/")
        self.setStyleSheet(theme.QSS)
        self.setMinimumWidth(400)
        self.setWindowTitle("Modifier l'agent" if agent else "Ajouter un agent")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(6)
        title = QLabel("✏️ Modifier l'agent" if agent else "➕ Nouvel agent")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        # Photo de profil (lecture seule : seul l'agent la change, depuis son
        # portail). Initiales par défaut, remplacées si une photo existe.
        if agent:
            size = 72
            photo = QLabel(_avatar_initials(agent.get("name")))
            photo.setFixedSize(size, size)
            photo.setAlignment(Qt.AlignCenter)
            photo.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {theme.ACCENT}, stop:1 #1b3a6b);"
                f" color: white; border-radius: {size // 2}px; font-weight: 800; font-size: 24px;")
            photo_row = QHBoxLayout()
            photo_row.addStretch()
            photo_row.addWidget(photo)
            photo_row.addStretch()
            root.addLayout(photo_row)
            start_avatar_load(self, photo, self.api_base, agent.get("avatar_url"), size)

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


class FalseAlarmDialog(QDialog):
    """Qualification d'une alerte en « fausse alerte » : motif obligatoire.

    L'action est tracée (auteur, rôle, heure, motif) et seul un superviseur ou
    un administrateur peut l'annuler.
    """

    REASONS = [
        "Canular / appel malveillant",
        "Erreur de manipulation du citoyen",
        "Aucun incident constaté sur place",
        "Doublon d'un incident déjà traité",
        "Test de l'application",
        "Autre (préciser)",
    ]

    def __init__(self, alert, parent=None, cancel_mode=False):
        super().__init__(parent)
        self.cancel_mode = cancel_mode
        self.setStyleSheet(theme.QSS + f"QDialog {{ background: {theme.BG}; }}")
        self.setMinimumWidth(460)
        ref = incident_ref(alert)
        self.setWindowTitle("Annuler la fausse alerte" if cancel_mode else "Signaler une fausse alerte")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(10)
        title = QLabel(("↩️  Annuler la qualification — " if cancel_mode
                        else "🚫  Fausse alerte — ") + f"#{ref}")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        info = QLabel(
            "Réservé au superviseur / administrateur. L'alerte redevient un incident "
            "normal ; la raison est inscrite au journal." if cancel_mode else
            "L'alerte sera clôturée et les ressources libérées. Le motif, votre nom et "
            "l'heure sont inscrits au journal. Le citoyen n'est PAS bloqué : ses "
            "prochaines alertes seront simplement signalées à l'opérateur.")
        info.setWordWrap(True)
        info.setObjectName("muted")
        root.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)
        self.reason = QComboBox()
        if not cancel_mode:
            self.reason.addItems(self.REASONS)
            form.addRow("Motif", self.reason)
        self.comment = QLineEdit()
        self.comment.setPlaceholderText(
            "Raison de l'annulation (obligatoire)" if cancel_mode
            else "Précision (obligatoire si « Autre »)")
        form.addRow("Raison" if cancel_mode else "Précision", self.comment)
        root.addLayout(form)

        self.error = QLabel("")
        self.error.setStyleSheet("color: #ef4444; font-weight: 600;")
        root.addWidget(self.error)

        btns = QHBoxLayout()
        cancel = QPushButton("Annuler")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Confirmer" if cancel_mode else "🚫  Classer en fausse alerte")
        ok.setObjectName("warn" if cancel_mode else "danger")
        ok.clicked.connect(self._validate)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(ok)
        root.addLayout(btns)

    def reason_text(self):
        comment = self.comment.text().strip()
        if self.cancel_mode:
            return comment
        base = self.reason.currentText()
        if base.startswith("Autre"):
            return comment
        return f"{base} — {comment}" if comment else base

    def _validate(self):
        if len(self.reason_text()) < 3:
            self.error.setText("Le motif est obligatoire.")
            return
        self.accept()


class JournalDialog(QDialog):
    """Journal d'une intervention : chronologie horodatée des actions."""

    ICONS = {
        "alert_created": "🚨", "alert_grouped": "🔁", "team_assigned": "🚔",
        "agent_assigned": "👮", "intervention_accepted": "✅",
        "intervention_completed": "🏁", "alert_closed": "🏁",
        "false_alarm_marked": "🚫", "false_alarm_cancelled": "↩️",
    }

    def __init__(self, alert, events, parent=None):
        super().__init__(parent)
        self.alert = alert
        self.events = events or []
        self.setStyleSheet(theme.QSS + f"QDialog {{ background: {theme.BG}; }}")
        self.setMinimumSize(620, 460)
        ref = incident_ref(alert)
        self.setWindowTitle(f"Journal de l'intervention #{ref}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(10)
        title = QLabel(f"📜  Journal de l'intervention #{ref}")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        sub = QLabel(f"{TYPE_NAMES.get(alert.get('type'), (alert.get('type') or '').capitalize())}"
                     f"  ·  {alert.get('neighborhood') or '—'}  ·  "
                     f"{len(self.events)} action{'s' if len(self.events) > 1 else ''} tracée"
                     f"{'s' if len(self.events) > 1 else ''}")
        sub.setObjectName("muted")
        root.addWidget(sub)

        from PySide6.QtWidgets import QScrollArea

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setSpacing(8)
        lay.setContentsMargins(0, 0, 6, 0)
        for ev in self.events:
            lay.addWidget(self._row(ev))
        if not self.events:
            empty = QLabel("Aucune action enregistrée.")
            empty.setObjectName("muted")
            lay.addWidget(empty)
        lay.addStretch()
        area.setWidget(holder)
        root.addWidget(area, 1)

        btns = QHBoxLayout()
        copy = QPushButton("📋  Copier le journal")
        copy.setObjectName("ghost")
        copy.clicked.connect(self._copy)
        self.btn_copy = copy
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        btns.addWidget(copy)
        btns.addStretch()
        btns.addWidget(close)
        root.addLayout(btns)

    def _row(self, ev):
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {theme.PANEL}; border: 1px solid {theme.BORDER};"
                           " border-radius: 10px; }} QLabel { border: none; background: transparent; }")
        h = QHBoxLayout(card)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(12)
        icon = QLabel(self.ICONS.get(ev.get("action"), "•"))
        icon.setStyleSheet("font-size: 20px;")
        h.addWidget(icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        head = QLabel(f"<b>{ev.get('label') or ev.get('action')}</b>")
        col.addWidget(head)
        who = QLabel(f"{ev.get('actor') or '—'}  ·  {ev.get('role') or '—'}"
                     + (f"  ·  IP {ev['ip']}" if ev.get("ip") else ""))
        who.setStyleSheet(f"color: {theme.MUTED};")
        col.addWidget(who)
        if ev.get("detail"):
            det = QLabel(str(ev["detail"]))
            det.setWordWrap(True)
            col.addWidget(det)
        h.addLayout(col, 1)
        when = QLabel(ev.get("time") or "—")
        when.setStyleSheet("font-weight: 700; font-family: Consolas, 'DejaVu Sans Mono', monospace;")
        h.addWidget(when, 0, Qt.AlignTop)
        return card

    def text(self):
        lines = [f"Journal de l'intervention #{incident_ref(self.alert)}"]
        for ev in self.events:
            line = f"{ev.get('time')}  {ev.get('label')}  —  {ev.get('actor')} ({ev.get('role')})"
            if ev.get("detail"):
                line += f"  ·  {ev['detail']}"
            lines.append(line)
        return "\n".join(lines)

    def _copy(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.text())
        self.btn_copy.setText("✓  Journal copié")


class ProfileDialog(QDialog):
    """Fiche d'identité d'un citoyen (lecture seule) : photo de profil, nom,
    téléphone, e-mail, date d'inscription.

    Le poste opérateur ne modifie jamais cette photo — seul le citoyen la
    gère, depuis son application (droit à l'image / vie privée)."""

    def __init__(self, person, parent=None, api_base=""):
        super().__init__(parent)
        self.api_base = (api_base or "").rstrip("/")
        self.setStyleSheet(theme.QSS + f"QDialog {{ background: {theme.BG}; }}")
        self.setMinimumWidth(360)
        self.setWindowTitle("Profil du citoyen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        size = 88
        self.photo = QLabel(_avatar_initials(person.get("name")))
        self.photo.setFixedSize(size, size)
        self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {theme.ACCENT}, stop:1 #1b3a6b);"
            f" color: white; border-radius: {size // 2}px; font-weight: 800; font-size: 30px;")
        photo_row = QHBoxLayout()
        photo_row.addStretch()
        photo_row.addWidget(self.photo)
        photo_row.addStretch()
        root.addLayout(photo_row)
        start_avatar_load(self, self.photo, self.api_base, person.get("avatar_url"), size)

        name = QLabel(person.get("name") or "Citoyen")
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet("font-size: 18px; font-weight: 800;")
        root.addWidget(name)

        info = QGridLayout()
        info.setVerticalSpacing(8)
        info.setHorizontalSpacing(14)
        rows = [
            ("Téléphone", person.get("phone") or "—"),
            ("Email", person.get("email") or "—"),
            ("Inscrit le", (person.get("created_at") or "—")[:10]),
        ]
        for i, (label, value) in enumerate(rows):
            kl = QLabel(label + " :")
            kl.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
            vl = QLabel(str(value))
            vl.setWordWrap(True)
            vl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            vl.setStyleSheet("font-weight: 700;")
            info.addWidget(kl, i, 0, Qt.AlignTop)
            info.addWidget(vl, i, 1)
        root.addLayout(info)

        btns = QHBoxLayout()
        btns.addStretch()
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        root.addLayout(btns)
