"""SlopeForge's compact, semantic Qt Widgets presentation theme."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication


class Color:
    APP_BACKGROUND = "#f4f6f9"
    SURFACE = "#ffffff"
    SURFACE_SUBTLE = "#f8fafc"
    BORDER = "#d7dde6"
    SEPARATOR = "#c5ccd5"
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#374151"
    TEXT_MUTED = "#6b7280"
    ACCENT = "#1261a0"
    ACCENT_HOVER = "#0b4f86"
    SELECTED = "#eaf3ff"
    FOCUS = "#0b63ce"
    SUCCESS = "#2f6f3e"
    WARNING = "#8a5a00"
    ERROR = "#a33a32"
    DISABLED = "#9ca3af"


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    PAGE = 10
    CARD_HORIZONTAL = 14
    CARD_VERTICAL = 12
    RADIUS = 7


APPLICATION_STYLESHEET = """
QMainWindow, QDialog { background: #f4f6f9; color: #111827; }
QWidget#DashboardPage { background: #f4f6f9; }
QFrame#CardFrame, QFrame#DashboardCard, QFrame#DashboardMetricCard,
QFrame#DashboardHeaderCard, QFrame#ConnectionCard, QFrame#EngineeringCard,
QFrame#CriterionCard, QFrame#ResultCard {
    background: #ffffff; border: 1px solid #d7dde6; border-radius: 7px;
}
QFrame#DashboardSummaryRow, QWidget#ProjectLinesDatasetRow, QWidget#StandardRow {
    background: #ffffff; border: 1px solid #d7dde6; border-radius: 5px;
}
QLabel#EntityTitle, QLabel#BlockTitle { color: #111827; font-size: 22px; font-weight: 700; }
QLabel#CardTitle, QLabel#EngineeringSectionTitle, QLabel#RelatedEntityTitle,
QLabel#SectionTitle { color: #1f2937; font-weight: 600; }
QLabel#MutedText, QLabel#EntityContextLine, QLabel#CalculatedCaption { color: #6b7280; }
QLabel#SummaryValue, QLabel#ActivityTitle { color: #111827; font-weight: 600; }
QLabel#EngineeringSummaryText { color: #374151; }
QFrame#OverviewDivider { color: #e5e7eb; background: #e5e7eb; max-height: 1px; border: 0; }

QPushButton { min-height: 26px; padding: 2px 10px; }
QPushButton[role="primary"] { color: white; background: #1261a0; border: 1px solid #1261a0; border-radius: 5px; font-weight: 600; }
QPushButton[role="primary"]:hover { background: #0b4f86; }
QPushButton[role="secondary"] { color: #1f2937; background: #ffffff; border: 1px solid #c5ccd5; border-radius: 5px; }
QPushButton[role="secondary"]:hover { color: #1261a0; border-color: #1261a0; background: #f8fafc; }
QPushButton[role="link"] { color: #1261a0; background: transparent; border: 0; padding: 2px 4px; font-weight: 600; }
QPushButton[role="link"]:hover { color: #0b4f86; text-decoration: underline; }
QPushButton[role="danger"] { color: #a33a32; background: #ffffff; border: 1px solid #d9a6a2; border-radius: 5px; }
QPushButton:disabled { color: #9ca3af; }

QTabWidget[entityTabs="true"]::pane { border: 0; background: transparent; top: -1px; }
QTabWidget[entityTabs="true"] QTabBar::tab {
    color: #6b7280; background: transparent; border: 0; border-bottom: 2px solid transparent;
    padding: 7px 12px; margin-right: 2px;
}
QTabWidget[entityTabs="true"] QTabBar::tab:selected { color: #1261a0; border-bottom-color: #1261a0; font-weight: 600; }
QTabWidget[entityTabs="true"] QTabBar::tab:hover:!selected { color: #374151; background: #f8fafc; }
QTabWidget[entityTabs="true"] QTabBar::tab:focus { outline: 1px solid #0b63ce; }

QLabel#StatusBadge { border-radius: 5px; padding: 3px 7px; font-weight: 600; }
QLabel#StatusBadge[statusRole="neutral"] { background: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db; }
QLabel#StatusBadge[statusRole="info"] { background: #eaf3ff; color: #155fa0; border: 1px solid #9bc2e8; }
QLabel#StatusBadge[statusRole="warning"] { background: #fff4d6; color: #8a5a00; border: 1px solid #f4c76b; }
QLabel#StatusBadge[statusRole="success"] { background: #edf8f0; color: #2f6f3e; border: 1px solid #9bcaa6; }
QLabel#StatusBadge[statusRole="error"] { background: #fff0f0; color: #a33a32; border: 1px solid #e0aaa5; }
QLabel#StatusBadge[statusRole="archived"] { background: #eef0f3; color: #4b5563; border: 1px solid #cfd4dc; }
QLabel#StaleBadge { background: #fff1c2; color: #8a5a00; border: 1px solid #e5b94d; border-radius: 4px; padding: 2px 5px; }

QListWidget#SettingsNavigation { background: #f8fafc; border: 1px solid #d7dde6; border-radius: 6px; padding: 4px; }
QListWidget#SettingsNavigation::item { min-height: 28px; padding: 3px 8px; border-left: 3px solid transparent; }
QListWidget#SettingsNavigation::item:selected { color: #1261a0; background: #eaf3ff; border-left-color: #1261a0; }
QListWidget#SettingsNavigation::item:hover:!selected { background: #ffffff; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #0b63ce; }
"""

# Compatibility value for small widgets that cannot inherit the application
# stylesheet (for example, independently rendered row delegates).
STANDARD_ROW_STYLESHEET = (
    "background:#ffffff;border:1px solid #d7dde6;border-radius:5px;"
)


def apply_theme(app: QApplication) -> None:
    """Apply the presentation-only theme once, before any application dialogs."""
    app.setStyleSheet(APPLICATION_STYLESHEET)
