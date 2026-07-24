"""Thème « centre de commandement » pour le poste opérateur SafeCity.

Centralise la palette de couleurs et la feuille de style Qt (QSS). Deux modes :
**sombre** (défaut) et **clair**, commutables à chaud via `set_mode()`.
"""

# --- Palettes (sombre / clair) ---
DARK = dict(
    BG="#0b1220", BG_ALT="#111a2e", PANEL="#16223c", PANEL_2="#1c2b48",
    SIDEBAR="#0d1526", BORDER="#233250", TEXT="#e6ecf5", MUTED="#8595b4",
    ACCENT="#3d8bff", ACCENT_2="#5eead4",
)
LIGHT = dict(
    BG="#eef2f8", BG_ALT="#f4f7fb", PANEL="#ffffff", PANEL_2="#eaf0f8",
    SIDEBAR="#e2e9f4", BORDER="#d3dcea", TEXT="#16223c", MUTED="#5a6b8c",
    ACCENT="#2563eb", ACCENT_2="#0e9488",
)

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
    "assignee": "#eab308",
    "cloturee": "#22c55e",
}
STATUS_LABELS = {
    "active": "En cours",
    "assignee": "Affectée",
    "cloturee": "Résolue",
}


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

/* --- Menu latéral --- */
QFrame#sidebar {{
    background: {p['SIDEBAR']};
    border-right: 1px solid {p['BORDER']};
}}
QLabel#brand {{ font-size: 20px; font-weight: 800; color: {p['TEXT']}; }}
QLabel#brandSub {{ font-size: 11px; color: {p['MUTED']}; }}

QPushButton#navBtn {{
    text-align: left;
    padding: 12px 12px;
    border: none;
    border-radius: 10px;
    background: transparent;
    color: {p['MUTED']};
    font-size: 13.5px;
    font-weight: 600;
}}
QPushButton#navBtn:hover {{ background: {p['PANEL']}; color: {p['TEXT']}; }}
QPushButton#navBtn:checked {{
    background: {p['ACCENT']};
    color: white;
}}
QPushButton#logoutBtn {{
    text-align: left; padding: 12px 16px; border: none; border-radius: 10px;
    background: transparent; color: #ff8181; font-size: 14px; font-weight: 600;
}}
QPushButton#logoutBtn:hover {{ background: rgba(239,68,68,0.15); }}

/* --- Barre supérieure --- */
QFrame#topbar {{ background: {p['BG_ALT']}; border-bottom: 1px solid {p['BORDER']}; }}
QLabel#pageTitle {{ font-size: 22px; font-weight: 800; }}
QLabel#clock {{ color: {p['MUTED']}; font-size: 13px; }}

/* --- Cartes / panneaux --- */
QFrame#card, QFrame#panel {{
    background: {p['PANEL']};
    border: 1px solid {p['BORDER']};
    border-radius: 16px;
}}
QLabel#cardValue {{ font-size: 30px; font-weight: 800; }}
QLabel#cardLabel {{ color: {p['MUTED']}; font-size: 12px; font-weight: 600; }}
QLabel#sectionTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#muted {{ color: {p['MUTED']}; }}

/* --- Tableaux --- */
QTableWidget {{
    background: {p['PANEL']};
    border: 1px solid {p['BORDER']};
    border-radius: 12px;
    gridline-color: {p['BORDER']};
    selection-background-color: {p['ACCENT']};
}}
QHeaderView::section {{
    background: {p['BG_ALT']};
    color: {p['MUTED']};
    padding: 10px;
    border: none;
    border-bottom: 1px solid {p['BORDER']};
    font-weight: 700;
}}
QTableWidget::item {{ padding: 6px; border-bottom: 1px solid {p['BORDER']}; }}

/* --- Boutons --- */
QPushButton {{
    background: {p['ACCENT']};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 700;
}}
QPushButton:hover {{ background: #529bff; }}
QPushButton:disabled {{ background: {p['BORDER']}; color: {p['MUTED']}; }}
QPushButton#ghost {{ background: {p['PANEL']}; color: {p['TEXT']}; border: 1px solid {p['BORDER']}; }}
QPushButton#ghost:hover {{ background: {p['BG_ALT']}; }}
QPushButton#danger {{ background: #ef4444; }}
QPushButton#danger:hover {{ background: #f56565; }}
QPushButton#success {{ background: #22c55e; }}
QPushButton#warn {{ background: #eab308; color: #1a1400; }}

/* --- Champs --- */
QLineEdit, QComboBox {{
    background: {p['BG_ALT']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    padding: 10px 12px;
    color: {p['TEXT']};
    selection-background-color: {p['ACCENT']};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {p['ACCENT']}; }}
QComboBox QAbstractItemView {{
    background: {p['PANEL']}; border: 1px solid {p['BORDER']};
    selection-background-color: {p['ACCENT']};
}}

/* --- Barres de défilement --- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['BORDER']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['MUTED']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

/* --- Barre d'état --- */
QFrame#statusbar {{ background: {p['BG_ALT']}; border-top: 1px solid {p['BORDER']}; }}
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


# Initialise QSS avec le thème par défaut (sombre) au chargement du module.
QSS = _build_qss(DARK)
