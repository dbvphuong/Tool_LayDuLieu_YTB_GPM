"""Theme, color palette, and Qt Style Sheet (QSS) for YTB GPM Collector.

Design philosophy:
- Soft Slate & Calm Blue modern desktop SaaS look
- High contrast, eye-friendly for long-term usage (WCAG AA compliant)
- Clean card-based surfaces with smooth micro-borders and rounded corners
"""

from pathlib import Path
from typing import Dict

# ---------------------------------------------------------------------------
# ASSET RESOURCES
# ---------------------------------------------------------------------------
RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
CHEVRON_DOWN_SVG = (RESOURCES_DIR / "chevron-down.svg").as_posix()
CHEVRON_UP_SVG = (RESOURCES_DIR / "chevron-up.svg").as_posix()
CALENDAR_SVG = (RESOURCES_DIR / "calendar.svg").as_posix()

# ---------------------------------------------------------------------------
# COLOR PALETTE
# ---------------------------------------------------------------------------
COLOR_BG_MAIN = "#F1F5F9"        # Slate Light Background
COLOR_BG_SIDEBAR = "#1E293B"     # Navy Slate Dark
COLOR_BG_SIDEBAR_HOVER = "#334155" # Navy Slate Lighter (Hover)
COLOR_BG_SIDEBAR_ACTIVE = "#2563EB" # Calm Royal Blue (Active Nav Item)
COLOR_BG_CARD = "#FFFFFF"        # Pure White Card
COLOR_BG_CARD_ALT = "#F8FAFC"    # Subtle Slate Card / Table Alternate
COLOR_BG_INPUT = "#FFFFFF"       # Input Background
COLOR_BG_DARK_LOG = "#0F172A"    # Deep Slate / Dark Terminal Background

# Brand & Accents
COLOR_PRIMARY = "#2563EB"        # Calm Royal Blue
COLOR_PRIMARY_HOVER = "#3B82F6"  # Ocean Blue Hover
COLOR_PRIMARY_PRESSED = "#1D4ED8" # Dark Royal Blue Pressed
COLOR_ACCENT = "#0EA5E9"         # Sky Blue Accent

# Typography
COLOR_TEXT_MAIN = "#0F172A"      # Dark Slate Text (Primary titles, data)
COLOR_TEXT_MUTED = "#64748B"     # Muted Gray Text (Labels, captions)
COLOR_TEXT_LIGHT = "#F8FAFC"     # White / Light Text for Dark Surfaces
COLOR_TEXT_SIDEBAR_MUTED = "#94A3B8" # Muted Text in Navy Sidebar

# Borders
COLOR_BORDER = "#CBD5E1"         # Standard Slate Border
COLOR_BORDER_LIGHT = "#E2E8F0"   # Light Slate Border
COLOR_BORDER_FOCUS = "#2563EB"   # Active Focus Border

# Status & Badges
COLOR_SUCCESS = "#059669"        # Emerald Green
COLOR_SUCCESS_BG = "#ECFDF5"     # Soft Green Tint
COLOR_SUCCESS_BORDER = "#A7F3D0"

COLOR_WARNING = "#D97706"        # Amber Warning
COLOR_WARNING_BG = "#FFFBEB"     # Soft Amber Tint
COLOR_WARNING_BORDER = "#FDE68A"

COLOR_DANGER = "#DC2626"         # Crimson Danger
COLOR_DANGER_BG = "#FEF2F2"      # Soft Red Tint
COLOR_DANGER_BORDER = "#FECACA"

COLOR_INFO = "#2563EB"           # Slate Blue Info
COLOR_INFO_BG = "#EFF6FF"        # Soft Blue Tint
COLOR_INFO_BORDER = "#BFDBFE"

# System Fonts
FONT_FAMILY_UI = '"Segoe UI", Arial, sans-serif'
FONT_FAMILY_MONO = '"Consolas", "Courier New", monospace'


def get_application_stylesheet() -> str:
    """Returns the unified Soft Blue / Navy Slate Qt Style Sheet."""
    return f"""
    /* ========================================================================= */
    /* GLOBAL RESET & BASE STYLES                                               */
    /* ========================================================================= */
    QWidget {{
        font-family: {FONT_FAMILY_UI};
        font-size: 13px;
        color: {COLOR_TEXT_MAIN};
        outline: none;
    }}

    QMainWindow, QDialog {{
        background-color: {COLOR_BG_MAIN};
    }}

    QMessageBox {{
        background-color: #FFFFFF;
    }}

    QMessageBox QLabel {{
        color: {COLOR_TEXT_MAIN};
    }}

    /* Context Menus & Action Popups */
    QMenu {{
        background-color: #FFFFFF;
        color: {COLOR_TEXT_MAIN};
        border: 1px solid {COLOR_BORDER};
        padding: 4px;
    }}

    QMenu::item {{
        background-color: transparent;
        color: {COLOR_TEXT_MAIN};
        padding: 6px 20px 6px 12px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {COLOR_INFO_BG};
        color: {COLOR_PRIMARY};
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {COLOR_BORDER_LIGHT};
        margin: 4px 8px;
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {COLOR_TEXT_MAIN};
        color: #FFFFFF;
        border: 1px solid #334155;
        border-radius: 4px;
        padding: 5px 8px;
        font-size: 12px;
    }}

    /* ========================================================================= */
    /* SIDEBAR NAVIGATION                                                       */
    /* ========================================================================= */
    QWidget#sidebarWidget {{
        background-color: {COLOR_BG_SIDEBAR};
        border-right: 1px solid #0F172A;
    }}

    QLabel#sidebarBrandTitle {{
        color: #FFFFFF;
        font-size: 17px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}

    QLabel#sidebarBrandSubtitle {{
        color: {COLOR_TEXT_SIDEBAR_MUTED};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    QLabel#sidebarBrandBadge {{
        background-color: #0F172A;
        color: #38BDF8;
        font-size: 10px;
        font-weight: 700;
        border-radius: 4px;
        padding: 2px 6px;
        border: 1px solid #334155;
    }}

    /* Navigation Buttons */
    QPushButton.nav-btn {{
        background-color: transparent;
        color: {COLOR_TEXT_SIDEBAR_MUTED};
        border: none;
        border-radius: 8px;
        padding: 10px 14px;
        text-align: left;
        font-size: 13px;
        font-weight: 500;
    }}

    QPushButton.nav-btn:hover {{
        background-color: {COLOR_BG_SIDEBAR_HOVER};
        color: #FFFFFF;
    }}

    QPushButton.nav-btn:checked {{
        background-color: {COLOR_PRIMARY};
        color: #FFFFFF;
        font-weight: 600;
    }}

    /* Sidebar Footer & Status Card */
    QFrame#sidebarStatusCard {{
        background-color: #0F172A;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 10px;
    }}

    QLabel#sidebarStatusPort {{
        color: #E2E8F0;
        font-size: 12px;
        font-weight: 600;
    }}

    QLabel#sidebarStatusText {{
        color: {COLOR_TEXT_SIDEBAR_MUTED};
        font-size: 11px;
    }}

    /* ========================================================================= */
    /* CONTENT AREA & CARDS                                                      */
    /* ========================================================================= */
    QStackedWidget#contentStack {{
        background-color: {COLOR_BG_MAIN};
    }}

    QWidget.page-container {{
        background-color: {COLOR_BG_MAIN};
    }}

    /* Page Header */
    QLabel.page-title {{
        color: {COLOR_TEXT_MAIN};
        font-size: 20px;
        font-weight: 700;
    }}

    QLabel.page-subtitle {{
        color: {COLOR_TEXT_MUTED};
        font-size: 13px;
    }}

    /* Card Panels */
    QFrame.card {{
        background-color: {COLOR_BG_CARD};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 10px;
    }}

    QLabel.card-title {{
        color: {COLOR_TEXT_MAIN};
        font-size: 15px;
        font-weight: 600;
    }}

    QLabel.card-subtitle {{
        color: {COLOR_TEXT_MUTED};
        font-size: 12px;
    }}

    /* Group Box */
    QGroupBox {{
        background-color: {COLOR_BG_CARD};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 8px;
        margin-top: 14px;
        padding-top: 14px;
        font-weight: 600;
        color: {COLOR_TEXT_MAIN};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 6px;
        color: {COLOR_TEXT_MAIN};
    }}

    /* ========================================================================= */
    /* BUTTONS                                                                   */
    /* ========================================================================= */
    QPushButton {{
        background-color: #FFFFFF;
        color: {COLOR_TEXT_MAIN};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: 7px 16px;
        font-size: 13px;
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: {COLOR_BG_CARD_ALT};
        border-color: #94A3B8;
    }}

    QPushButton:pressed {{
        background-color: #E2E8F0;
    }}

    QPushButton:disabled {{
        background-color: #F1F5F9;
        color: #94A3B8;
        border-color: #E2E8F0;
    }}

    /* Primary Button (Royal Blue) */
    QPushButton.primary-btn, QPushButton[btnType="primary"] {{
        background-color: {COLOR_PRIMARY};
        color: #FFFFFF;
        border: 1px solid {COLOR_PRIMARY};
        font-weight: 600;
    }}

    QPushButton.primary-btn:hover, QPushButton[btnType="primary"]:hover {{
        background-color: {COLOR_PRIMARY_HOVER};
        border-color: {COLOR_PRIMARY_HOVER};
    }}

    QPushButton.primary-btn:pressed, QPushButton[btnType="primary"]:pressed {{
        background-color: {COLOR_PRIMARY_PRESSED};
        border-color: {COLOR_PRIMARY_PRESSED};
    }}

    QPushButton.primary-btn:disabled, QPushButton[btnType="primary"]:disabled {{
        background-color: #93C5FD;
        border-color: #93C5FD;
        color: #EFF6FF;
    }}

    /* Success Button (Emerald Green) */
    QPushButton.success-btn, QPushButton[btnType="success"] {{
        background-color: {COLOR_SUCCESS};
        color: #FFFFFF;
        border: 1px solid {COLOR_SUCCESS};
        font-weight: 600;
    }}

    QPushButton.success-btn:hover, QPushButton[btnType="success"]:hover {{
        background-color: #10B981;
        border-color: #10B981;
    }}

    /* Danger Button (Crimson) */
    QPushButton.danger-btn, QPushButton[btnType="danger"] {{
        background-color: {COLOR_DANGER};
        color: #FFFFFF;
        border: 1px solid {COLOR_DANGER};
        font-weight: 600;
    }}

    QPushButton.danger-btn:hover, QPushButton[btnType="danger"]:hover {{
        background-color: #EF4444;
        border-color: #EF4444;
    }}

    /* Large Prominent Action Button */
    QPushButton[btnSize="large"] {{
        padding: 10px 24px;
        font-size: 14px;
        font-weight: 700;
        border-radius: 8px;
        min-height: 24px;
    }}

    /* Outline / Secondary Button */
    QPushButton[btnType="outline"] {{
        background-color: #FFFFFF;
        color: {COLOR_PRIMARY};
        border: 1.5px solid {COLOR_PRIMARY};
        font-weight: 600;
    }}

    QPushButton[btnType="outline"]:hover {{
        background-color: {COLOR_INFO_BG};
    }}

    /* ========================================================================= */
    /* FORM INPUTS (LineEdit, SpinBox, DateEdit)                                 */
    /* ========================================================================= */
    QLineEdit, QSpinBox, QDateEdit {{
        background-color: {COLOR_BG_INPUT};
        color: {COLOR_TEXT_MAIN};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: 6px 10px;
        min-height: 20px;
        selection-background-color: {COLOR_INFO_BORDER};
        selection-color: {COLOR_TEXT_MAIN};
    }}

    QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {{
        border: 1.5px solid {COLOR_BORDER_FOCUS};
    }}

    QLineEdit:disabled, QSpinBox:disabled, QDateEdit:disabled {{
        background-color: #F8FAFC;
        color: #94A3B8;
        border-color: #E2E8F0;
    }}

    /* QSpinBox Buttons */
    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border;
        width: 20px;
        background-color: #F8FAFC;
        border-left: 1px solid {COLOR_BORDER_LIGHT};
    }}

    QSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 5px;
        border-bottom: 0.5px solid {COLOR_BORDER_LIGHT};
    }}

    QSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 5px;
        border-top: 0.5px solid {COLOR_BORDER_LIGHT};
    }}

    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background-color: {COLOR_INFO_BG};
    }}

    QSpinBox::up-arrow {{
        image: url("{CHEVRON_UP_SVG}");
        width: 9px;
        height: 9px;
    }}

    QSpinBox::down-arrow {{
        image: url("{CHEVRON_DOWN_SVG}");
        width: 9px;
        height: 9px;
    }}

    /* QDateEdit */
    QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 26px;
        border-left: 1px solid {COLOR_BORDER_LIGHT};
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
        background-color: #F8FAFC;
    }}

    QDateEdit::drop-down:hover {{
        background-color: {COLOR_INFO_BG};
    }}

    QDateEdit::down-arrow {{
        image: url("{CALENDAR_SVG}");
        width: 13px;
        height: 13px;
    }}

    /* QCalendarWidget */
    QCalendarWidget QWidget {{
        background-color: #FFFFFF;
        color: {COLOR_TEXT_MAIN};
    }}

    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background-color: #F8FAFC;
        border-bottom: 1px solid {COLOR_BORDER};
    }}

    QCalendarWidget QToolButton {{
        color: {COLOR_TEXT_MAIN};
        background-color: transparent;
        border: none;
        border-radius: 4px;
        padding: 4px;
        font-weight: 600;
    }}

    QCalendarWidget QToolButton:hover {{
        background-color: #E2E8F0;
    }}

    QCalendarWidget QTableView {{
        background-color: #FFFFFF;
        color: {COLOR_TEXT_MAIN};
        selection-background-color: {COLOR_INFO_BG};
        selection-color: {COLOR_PRIMARY};
    }}

    QCalendarWidget QHeaderView::section {{
        background-color: #F8FAFC;
        color: #475569;
        font-weight: 600;
        font-size: 11px;
        padding: 4px;
    }}

    /* ========================================================================= */
    /* COMBOBOX STYLING                                                          */
    /* ========================================================================= */
    QComboBox {{
        background-color: {COLOR_BG_INPUT};
        color: {COLOR_TEXT_MAIN};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: 6px 28px 6px 10px;
        min-height: 20px;
        selection-background-color: {COLOR_INFO_BORDER};
        selection-color: {COLOR_TEXT_MAIN};
    }}

    QComboBox:hover {{
        border-color: #94A3B8;
    }}

    QComboBox:focus {{
        border: 1.5px solid {COLOR_BORDER_FOCUS};
    }}

    QComboBox:disabled {{
        background-color: #F8FAFC;
        color: #94A3B8;
        border-color: #E2E8F0;
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 26px;
        border-left: 1px solid {COLOR_BORDER_LIGHT};
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
        background-color: #F8FAFC;
    }}

    QComboBox::drop-down:hover {{
        background-color: {COLOR_INFO_BG};
    }}

    QComboBox::down-arrow {{
        image: url("{CHEVRON_DOWN_SVG}");
        width: 12px;
        height: 12px;
    }}

    /* Popup list container & items (NO border-radius to prevent Windows DWM black box bug) */
    QComboBox QAbstractItemView,
    QComboBox QListView {{
        background-color: #FFFFFF;
        color: {COLOR_TEXT_MAIN};
        border: 1px solid {COLOR_BORDER};
        selection-background-color: {COLOR_INFO_BG};
        selection-color: {COLOR_PRIMARY};
        outline: none;
        padding: 4px;
    }}

    QComboBox QAbstractItemView::item,
    QComboBox QListView::item {{
        color: {COLOR_TEXT_MAIN};
        background-color: #FFFFFF;
        min-height: 28px;
        padding: 4px 8px;
        border-radius: 4px;
    }}

    QComboBox QAbstractItemView::item:hover,
    QComboBox QListView::item:hover {{
        background-color: #F1F5F9;
        color: {COLOR_TEXT_MAIN};
    }}

    QComboBox QAbstractItemView::item:selected,
    QComboBox QListView::item:selected {{
        background-color: {COLOR_INFO_BG};
        color: {COLOR_PRIMARY};
        font-weight: 600;
    }}

    /* ========================================================================= */
    /* CHECKBOX & RADIO BUTTON                                                   */
    /* ========================================================================= */
    QCheckBox, QRadioButton {{
        spacing: 8px;
        color: {COLOR_TEXT_MAIN};
        font-size: 13px;
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        width: 17px;
        height: 17px;
        border: 1.5px solid {COLOR_BORDER};
        background-color: #FFFFFF;
        border-radius: 4px;
    }}

    QRadioButton::indicator {{
        border-radius: 9px;
    }}

    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {COLOR_PRIMARY};
    }}

    QCheckBox::indicator:checked {{
        background-color: {COLOR_PRIMARY};
        border-color: {COLOR_PRIMARY};
        image: none; /* In QSS we can color it, or use SVG if available */
    }}

    QRadioButton::indicator:checked {{
        background-color: {COLOR_PRIMARY};
        border-color: {COLOR_PRIMARY};
    }}

    /* ========================================================================= */
    /* TABLE & LIST VIEW                                                         */
    /* ========================================================================= */
    QTableWidget, QTableView {{
        background-color: #FFFFFF;
        alternate-background-color: {COLOR_BG_CARD_ALT};
        gridline-color: {COLOR_BORDER_LIGHT};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 6px;
        selection-background-color: {COLOR_INFO_BG};
        selection-color: {COLOR_TEXT_MAIN};
        color: {COLOR_TEXT_MAIN};
        outline: none;
    }}

    QTableWidget::item, QTableView::item {{
        color: {COLOR_TEXT_MAIN};
        padding: 4px 6px;
    }}

    QTableWidget::item:selected, QTableView::item:selected {{
        background-color: {COLOR_INFO_BG};
        color: {COLOR_TEXT_MAIN};
    }}

    QHeaderView::section {{
        background-color: #F8FAFC;
        color: #475569;
        font-weight: 600;
        font-size: 12px;
        padding: 8px 10px;
        border: none;
        border-bottom: 1.5px solid {COLOR_BORDER};
        border-right: 1px solid {COLOR_BORDER_LIGHT};
    }}

    QHeaderView::section:last {{
        border-right: none;
    }}

    /* ========================================================================= */
    /* PROGRESS BAR                                                              */
    /* ========================================================================= */
    QProgressBar {{
        background-color: #E2E8F0;
        border: none;
        border-radius: 6px;
        height: 14px;
        text-align: center;
        font-size: 11px;
        font-weight: 600;
        color: {COLOR_TEXT_MAIN};
    }}

    QProgressBar::chunk {{
        background-color: {COLOR_PRIMARY};
        border-radius: 6px;
    }}

    /* ========================================================================= */
    /* TEXT EDIT & LOG VIEW                                                      */
    /* ========================================================================= */
    QTextEdit, QPlainTextEdit {{
        background-color: #FFFFFF;
        color: {COLOR_TEXT_MAIN};
        border: 1px solid {COLOR_BORDER_LIGHT};
        border-radius: 6px;
        padding: 8px;
    }}

    QTextEdit#liveLogsTerminal, QPlainTextEdit#liveLogsTerminal {{
        background-color: {COLOR_BG_DARK_LOG};
        color: #F8FAFC;
        border: 1px solid #1E293B;
        border-radius: 8px;
        font-family: {FONT_FAMILY_MONO};
        font-size: 12px;
        line-height: 1.4;
        padding: 12px;
        selection-background-color: #334155;
    }}

    /* ========================================================================= */
    /* SCROLLBARS                                                                */
    /* ========================================================================= */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background-color: #CBD5E1;
        min-height: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: #94A3B8;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: #CBD5E1;
        min-width: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: #94A3B8;
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ========================================================================= */
    /* STATUS BADGES / LABELS                                                    */
    /* ========================================================================= */
    QLabel.badge-info {{
        background-color: {COLOR_INFO_BG};
        color: {COLOR_INFO};
        border: 1px solid {COLOR_INFO_BORDER};
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel.badge-success {{
        background-color: {COLOR_SUCCESS_BG};
        color: {COLOR_SUCCESS};
        border: 1px solid {COLOR_SUCCESS_BORDER};
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel.badge-warning {{
        background-color: {COLOR_WARNING_BG};
        color: {COLOR_WARNING};
        border: 1px solid {COLOR_WARNING_BORDER};
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel.badge-danger {{
        background-color: {COLOR_DANGER_BG};
        color: {COLOR_DANGER};
        border: 1px solid {COLOR_DANGER_BORDER};
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
    }}
    """
