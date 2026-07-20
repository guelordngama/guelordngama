"""Thème sombre « centre de commandement » pour le poste opérateur SafeCity.

Centralise la palette de couleurs et la feuille de style Qt (QSS). Un design
sombre bleu nuit, coins arrondis, accents colorés selon la gravité.
"""

# --- Palette ---
BG = "#0b1220"           # fond principal (bleu-noir)
BG_ALT = "#111a2e"       # fond secondaire
PANEL = "#16223c"        # cartes / panneaux
PANEL_2 = "#1c2b48"      # variante de panneau
SIDEBAR = "#0d1526"      # menu latéral
BORDER = "#233250"
TEXT = "#e6ecf5"         # texte principal
MUTED = "#8595b4"        # texte secondaire
ACCENT = "#3d8bff"       # bleu accent
ACCENT_2 = "#5eead4"     # cyan/vert

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


QSS = f"""
* {{
    font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
    color: {TEXT};
    outline: none;
}}
QWidget#root {{ background: {BG}; }}

/* --- Menu latéral --- */
QFrame#sidebar {{
    background: {SIDEBAR};
    border-right: 1px solid {BORDER};
}}
QLabel#brand {{ font-size: 20px; font-weight: 800; color: {TEXT}; }}
QLabel#brandSub {{ font-size: 11px; color: {MUTED}; }}

QPushButton#navBtn {{
    text-align: left;
    padding: 12px 12px;
    border: none;
    border-radius: 10px;
    background: transparent;
    color: {MUTED};
    font-size: 13.5px;
    font-weight: 600;
}}
QPushButton#navBtn:hover {{ background: {PANEL}; color: {TEXT}; }}
QPushButton#navBtn:checked {{
    background: {ACCENT};
    color: white;
}}
QPushButton#logoutBtn {{
    text-align: left; padding: 12px 16px; border: none; border-radius: 10px;
    background: transparent; color: #ff8181; font-size: 14px; font-weight: 600;
}}
QPushButton#logoutBtn:hover {{ background: rgba(239,68,68,0.15); }}

/* --- Barre supérieure --- */
QFrame#topbar {{ background: {BG_ALT}; border-bottom: 1px solid {BORDER}; }}
QLabel#pageTitle {{ font-size: 22px; font-weight: 800; }}
QLabel#clock {{ color: {MUTED}; font-size: 13px; }}

/* --- Cartes / panneaux --- */
QFrame#card, QFrame#panel {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QLabel#cardValue {{ font-size: 30px; font-weight: 800; }}
QLabel#cardLabel {{ color: {MUTED}; font-size: 12px; font-weight: 600; }}
QLabel#sectionTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}

/* --- Tableaux --- */
QTableWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
}}
QHeaderView::section {{
    background: {BG_ALT};
    color: {MUTED};
    padding: 10px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 700;
}}
QTableWidget::item {{ padding: 6px; border-bottom: 1px solid {BORDER}; }}

/* --- Boutons --- */
QPushButton {{
    background: {ACCENT};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 700;
}}
QPushButton:hover {{ background: #529bff; }}
QPushButton:disabled {{ background: {BORDER}; color: {MUTED}; }}
QPushButton#ghost {{ background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER}; }}
QPushButton#ghost:hover {{ background: {BG_ALT}; }}
QPushButton#danger {{ background: #ef4444; }}
QPushButton#danger:hover {{ background: #f56565; }}
QPushButton#success {{ background: #22c55e; }}
QPushButton#warn {{ background: #eab308; color: #1a1400; }}

/* --- Champs --- */
QLineEdit, QComboBox {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox QAbstractItemView {{
    background: {PANEL}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}

/* --- Barres de défilement --- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QDialog {{ background: {BG}; }}
QMessageBox {{ background: {BG_ALT}; }}
"""
