"""Thème « centre de commandement » pour le poste opérateur SafeCity.

Centralise la palette de couleurs et la feuille de style Qt (QSS). Deux modes :
**sombre** (défaut) et **clair**, commutables à chaud via `set_mode()`.
"""

# --- Palettes (sombre / clair) ---
# Même système visuel que le site citoyen et le portail agents : surfaces claires,
# cartes blanches, accent bleu, et barre latérale navy (dans les deux modes).
DARK = dict(
    BG="#0b1220", BG_ALT="#0f1a2e", PANEL="#131f36", PANEL_2="#182843",
    SIDEBAR="#0a1426", BORDER="#22324f", TEXT="#e6ecf5", MUTED="#93a1bd",
    ACCENT="#3b82f6", ACCENT_2="#14b8a6",
)
LIGHT = dict(
    BG="#eef2f8", BG_ALT="#f5f7fb", PANEL="#ffffff", PANEL_2="#f1f5fb",
    SIDEBAR="#0f1f3d", BORDER="#e3e9f2", TEXT="#16223c", MUTED="#64748b",
    ACCENT="#2563eb", ACCENT_2="#0e9488",
)
# Couleurs de la barre latérale navy (identiques dans les deux modes).
SIDE_TEXT = "#c3cfe6"
SIDE_MUTED = "#7f93b8"

# Constantes de palette actives (mises à jour par set_mode). Valeurs par défaut
# = thème sombre ; renseignées réellement à l'appel de set_mode() en fin de module.
BG = DARK["BG"]; BG_ALT = DARK["BG_ALT"]; PANEL = DARK["PANEL"]; PANEL_2 = DARK["PANEL_2"]
SIDEBAR = DARK["SIDEBAR"]; BORDER = DARK["BORDER"]; TEXT = DARK["TEXT"]; MUTED = DARK["MUTED"]
ACCENT = DARK["ACCENT"]; ACCENT_2 = DARK["ACCENT_2"]
_MODE = "dark"

# Couleurs par niveau d'urgence.
URGENCY_COLORS = {
    "faible": "#22c55e",     # 🟢
    "moyenne": "#eab308",    # 🟡
    "haute": "#f97316",      # 🟠
    "critique": "#ef4444",   # 🔴
}
URGENCY_LABELS = {
    "faible": "Faible",
    "moyenne": "Moyen",
    "haute": "Élevé",
    "critique": "Critique",
}
STATUS_COLORS = {
    "active": "#ef4444",
    "assignee": "#f97316",
    "cloturee": "#22c55e",
}
STATUS_LABELS = {
    "active": "En attente",
    "assignee": "En cours",
    "cloturee": "Traité",
}


def tint(color, alpha):
    """Couleur translucide pour les QSS : « rgba(r,g,b,a) ».

    Attention : Qt lit un hexadécimal à 8 chiffres comme #AARRGGBB (alpha EN
    PREMIER) ; « #ef444422 » ne donne donc PAS un rouge transparent. On passe
    toujours par cette fonction pour les fonds teintés.
    """
    c = (color or "#000000").lstrip("#")[:6]
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def qtint(color, alpha):
    """Même chose que tint() mais renvoie un QColor (pour setBackground)."""
    from PySide6.QtGui import QColor
    c = QColor(color)
    c.setAlphaF(alpha)
    return c


def urgency_color(u):
    return URGENCY_COLORS.get(u, ACCENT)


def urgency_label(u):
    return URGENCY_LABELS.get(u, (u or "").capitalize())


def _build_qss(p):
    return f"""
* {{
    font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
    color: {p['TEXT']};
    outline: none;
}}
QWidget#root {{ background: {p['BG']}; }}
QStackedWidget {{ background: {p['BG']}; }}
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* --- Menu latéral (navy) --- */
QFrame#sidebar {{
    background: {p['SIDEBAR']};
    border: none;
}}
QFrame#sidebar QLabel {{ color: {SIDE_TEXT}; background: transparent; }}
QLabel#brand {{ font-size: 19px; font-weight: 800; color: white; }}
QLabel#brandSub {{
    font-size: 11px; font-weight: 700; color: #93c5fd;
    background: rgba(59,130,246,0.18); border-radius: 9px; padding: 2px 9px;
}}
QLabel#sideSection {{ font-size: 10.5px; font-weight: 800; color: {SIDE_MUTED}; letter-spacing: 1px; }}

QPushButton#navBtn {{
    text-align: left;
    padding: 9px 12px;
    border: none;
    border-radius: 10px;
    background: transparent;
    color: {SIDE_TEXT};
    font-size: 13.5px;
    font-weight: 600;
}}
QPushButton#navBtn:hover {{ background: rgba(255,255,255,0.07); color: white; }}
QPushButton#navBtn:checked {{
    background: {p['ACCENT']};
    color: white;
}}
QPushButton#logoutBtn {{
    text-align: left; padding: 11px 14px; border: none; border-radius: 10px;
    background: transparent; color: #fca5a5; font-size: 13.5px; font-weight: 600;
}}
QPushButton#logoutBtn:hover {{ background: rgba(239,68,68,0.16); }}

/* --- Barre supérieure --- */
QFrame#topbar {{ background: {p['PANEL']}; border-bottom: 1px solid {p['BORDER']}; }}
QLabel#pageTitle {{ font-size: 21px; font-weight: 800; }}
QFrame#userChip {{
    background: {p['BG_ALT']}; border: 1px solid {p['BORDER']}; border-radius: 20px;
}}
QLabel#avatar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p['ACCENT']}, stop:1 #1b3a6b);
    color: white; border-radius: 15px; font-weight: 800; font-size: 12px;
}}
QLabel#chipName {{ font-weight: 700; font-size: 13px; }}
QLabel#chipRole {{ color: {p['MUTED']}; font-size: 11px; }}
QLabel#clock {{ color: {p['MUTED']}; font-size: 13px; }}

/* --- Cartes / panneaux --- */
QFrame#card, QFrame#panel {{
    background: {p['PANEL']};
    border: 1px solid {p['BORDER']};
    border-radius: 16px;
}}
QLabel#pill {{ border-radius: 14px; padding: 6px 14px; font-weight: 700; }}
QLabel#cardValue {{ font-size: 30px; font-weight: 800; }}
QLabel#cardLabel {{ color: {p['MUTED']}; font-size: 12px; font-weight: 600; }}
QLabel#sectionTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#muted {{ color: {p['MUTED']}; }}

/* --- Tableaux --- */
QTableWidget {{
    background: {p['PANEL']};
    alternate-background-color: {p['BG_ALT']};
    border: 1px solid {p['BORDER']};
    border-radius: 12px;
    gridline-color: transparent;
    selection-background-color: rgba(37,99,235,0.18);
    selection-color: {p['TEXT']};
}}
QHeaderView::section {{
    background: {p['PANEL_2']};
    color: {p['MUTED']};
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid {p['BORDER']};
    font-weight: 700;
    font-size: 12px;
}}
QTableWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {p['BORDER']}; }}
QTableCornerButton::section {{ background: {p['PANEL_2']}; border: none; }}

/* --- Boutons --- */
QPushButton {{
    background: {p['ACCENT']};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 700;
}}
QPushButton:hover {{ background: #1d4ed8; }}
QPushButton:disabled {{ background: {p['BORDER']}; color: {p['MUTED']}; }}
QPushButton#ghost {{ background: {p['PANEL']}; color: {p['TEXT']}; border: 1px solid {p['BORDER']}; }}
QPushButton#ghost:hover {{ background: {p['BG_ALT']}; border: 1px solid {p['ACCENT']}; }}
QPushButton#danger {{ background: #ef4444; }}
QPushButton#danger:hover {{ background: #f56565; }}
QPushButton#success {{ background: #16a34a; }}
QPushButton#warn {{ background: #eab308; color: #1a1400; }}

/* --- Champs --- */
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDateEdit {{
    background: {p['PANEL']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    padding: 10px 12px;
    color: {p['TEXT']};
    selection-background-color: {p['ACCENT']};
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border: 1px solid {p['ACCENT']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {p['PANEL']}; border: 1px solid {p['BORDER']};
    selection-background-color: {p['ACCENT']};
}}

/* --- Barres de défilement --- */
/* Poignée bien visible et assez large pour être saisie ; rails transparents
   (sans eux Qt dessine un motif par défaut et le clic sur le rail saute). */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px 1px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 1px 2px; }}
QScrollBar::handle:vertical {{ background: {p['MUTED']}; border-radius: 5px; min-height: 36px; }}
QScrollBar::handle:horizontal {{ background: {p['MUTED']}; border-radius: 5px; min-width: 36px; }}
QScrollBar::handle:hover, QScrollBar::handle:pressed {{ background: {p['ACCENT']}; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; background: none; }}
QScrollArea#sideScroll, QScrollArea#sideScroll > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollArea#sideScroll QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.28); }}

/* --- Barre d'état --- */
QFrame#statusbar {{ background: {p['PANEL']}; border-top: 1px solid {p['BORDER']}; }}
QFrame#statusbar QLabel {{ color: {p['MUTED']}; font-size: 12px; }}

QDialog {{ background: {p['BG']}; }}
QMessageBox {{ background: {p['BG_ALT']}; }}
"""


def set_mode(mode):
    """Active le mode « light » ou « dark » : met à jour la palette et le QSS."""
    global _MODE, QSS, BG, BG_ALT, PANEL, PANEL_2, SIDEBAR, BORDER, TEXT, MUTED, ACCENT, ACCENT_2
    _MODE = "light" if mode == "light" else "dark"
    p = LIGHT if _MODE == "light" else DARK
    BG = p["BG"]; BG_ALT = p["BG_ALT"]; PANEL = p["PANEL"]; PANEL_2 = p["PANEL_2"]
    SIDEBAR = p["SIDEBAR"]; BORDER = p["BORDER"]; TEXT = p["TEXT"]; MUTED = p["MUTED"]
    ACCENT = p["ACCENT"]; ACCENT_2 = p["ACCENT_2"]
    QSS = _build_qss(p)
    return QSS


def current_mode():
    return _MODE


# Initialise QSS avec le thème par défaut (clair) au chargement du module.
set_mode("light")
