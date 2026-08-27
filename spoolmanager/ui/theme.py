"""Palette et feuille de style de l'application."""

from __future__ import annotations

from PySide6.QtGui import QColor

BG = "#14161A"
SURFACE = "#1D2026"
SURFACE_HI = "#262A32"
BORDER = "#333844"
TEXT = "#E6E9EF"
MUTED = "#98A0AE"
ACCENT = "#FF6A13"
ACCENT_DARK = "#D9550C"
SUCCESS = "#3DD68C"
WARNING = "#F5A524"
DANGER = "#F4585B"
INFO = "#4C9AFF"


def level_color(ratio: float, remaining_g: float, low_threshold: float) -> str:
    """Couleur de la jauge selon ce qu'il reste réellement, pas seulement le pourcentage."""
    if remaining_g <= 0.5:
        return DANGER
    if remaining_g <= low_threshold:
        return WARNING
    if ratio < 0.25:
        return WARNING
    return SUCCESS


def readable_text_on(hex_color: str) -> str:
    """Noir ou blanc selon la luminance du fond, pour rester lisible."""
    color = QColor(hex_color)
    if not color.isValid():
        return TEXT
    luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return "#111111" if luminance > 150 else "#FFFFFF"


def safe_color(hex_color: str, fallback: str = "#9E9E9E") -> str:
    color = QColor(hex_color or "")
    return color.name().upper() if color.isValid() else fallback


STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{ background-color: {BG}; }}

QLabel[role="title"] {{ font-size: 21px; font-weight: 600; }}
QLabel[role="subtitle"] {{ color: {MUTED}; font-size: 13px; }}
QLabel[role="section"] {{ font-size: 15px; font-weight: 600; padding-top: 4px; }}
QLabel[role="stat"] {{ font-size: 25px; font-weight: 700; }}
QLabel[role="statLabel"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="danger"] {{ color: {DANGER}; }}
QLabel[role="warning"] {{ color: {WARNING}; }}
QLabel[role="success"] {{ color: {SUCCESS}; }}

QFrame[role="card"] {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame[role="card"]:hover {{ border-color: #47506080; }}
QFrame[role="cardSelected"] {{
    background-color: {SURFACE_HI};
    border: 1px solid {ACCENT};
    border-radius: 12px;
}}
QFrame[role="slot"] {{
    background-color: {SURFACE};
    border: 1px dashed {BORDER};
    border-radius: 12px;
}}
QFrame[role="slotFilled"] {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame[role="slotDrop"] {{
    background-color: {SURFACE_HI};
    border: 2px dashed {ACCENT};
    border-radius: 12px;
}}
QFrame[role="banner"] {{
    background-color: #2A2118;
    border: 1px solid {WARNING};
    border-radius: 10px;
}}
QFrame[role="separator"] {{ background-color: {BORDER}; max-height: 1px; border: none; }}

QPushButton {{
    background-color: {SURFACE_HI};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: #2F3540; }}
QPushButton:pressed {{ background-color: #383F4C; }}
QPushButton:disabled {{ color: #5A6270; background-color: #1A1D23; }}

QPushButton[variant="primary"] {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: #14161A;
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background-color: #FF7E33; }}
QPushButton[variant="primary"]:pressed {{ background-color: {ACCENT_DARK}; }}
QPushButton[variant="danger"] {{ color: {DANGER}; }}
QPushButton[variant="danger"]:hover {{ background-color: #3A2124; }}
QPushButton[variant="ghost"] {{ background-color: transparent; border-color: transparent; }}
QPushButton[variant="ghost"]:hover {{ background-color: {SURFACE_HI}; }}

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE_HI};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: {ACCENT};
    selection-color: #14161A;
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus,
QDateEdit:focus, QTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_HI};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: #14161A;
    outline: none;
}}

QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 9px 18px;
    margin-right: 4px;
    border-radius: 8px;
    font-weight: 500;
}}
QTabBar::tab:selected {{ background-color: {SURFACE_HI}; color: {TEXT}; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

QTableWidget, QTreeWidget, QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: {BORDER};
    outline: none;
}}
QTableWidget::item, QTreeWidget::item, QListWidget::item {{ padding: 6px; }}
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: #33404F;
    color: {TEXT};
}}
QHeaderView::section {{
    background-color: {SURFACE_HI};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-weight: 600;
}}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3A414F; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #4A5364; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #3A414F; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {SURFACE_HI};
}}
QCheckBox::indicator:checked {{ background-color: {ACCENT}; border-color: {ACCENT}; }}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: {MUTED}; }}

QToolTip {{
    background-color: {SURFACE_HI};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px;
}}

QMenu {{
    background-color: {SURFACE_HI};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: {ACCENT}; color: #14161A; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
"""
