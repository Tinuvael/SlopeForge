"""Application-level appearance contract for SlopeForge.

SlopeForge currently ships one controlled light engineering theme.  Qt on
Windows can otherwise inherit the OS dark colour scheme for widgets that are
not fully painted by the application QSS, creating a mixed light/dark UI.
This module pins the native Qt colour scheme and palette before any dialogs are
constructed while leaving the existing semantic QSS in ``ui.theme`` intact.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ui.theme import Color


_ACTIVE_LIGHT_ROLES = {
    QPalette.ColorRole.Window: Color.APP_BACKGROUND,
    QPalette.ColorRole.WindowText: Color.TEXT_PRIMARY,
    QPalette.ColorRole.Base: Color.SURFACE,
    QPalette.ColorRole.AlternateBase: Color.SURFACE_SUBTLE,
    QPalette.ColorRole.ToolTipBase: Color.SURFACE,
    QPalette.ColorRole.ToolTipText: Color.TEXT_PRIMARY,
    QPalette.ColorRole.Text: Color.TEXT_PRIMARY,
    QPalette.ColorRole.Button: Color.SURFACE,
    QPalette.ColorRole.ButtonText: Color.TEXT_PRIMARY,
    QPalette.ColorRole.BrightText: "#ffffff",
    QPalette.ColorRole.Light: Color.SURFACE,
    QPalette.ColorRole.Midlight: Color.SURFACE_SUBTLE,
    QPalette.ColorRole.Dark: Color.BORDER,
    QPalette.ColorRole.Mid: Color.SEPARATOR,
    QPalette.ColorRole.Shadow: Color.TEXT_MUTED,
    QPalette.ColorRole.Highlight: Color.SELECTED,
    QPalette.ColorRole.HighlightedText: Color.TEXT_PRIMARY,
    QPalette.ColorRole.Link: Color.ACCENT,
    QPalette.ColorRole.LinkVisited: Color.ACCENT_HOVER,
    QPalette.ColorRole.PlaceholderText: Color.TEXT_MUTED,
}

_DISABLED_LIGHT_ROLES = {
    QPalette.ColorRole.Window: Color.APP_BACKGROUND,
    QPalette.ColorRole.WindowText: Color.DISABLED,
    QPalette.ColorRole.Base: Color.SURFACE_SUBTLE,
    QPalette.ColorRole.AlternateBase: Color.SURFACE_SUBTLE,
    QPalette.ColorRole.ToolTipBase: Color.SURFACE,
    QPalette.ColorRole.ToolTipText: Color.TEXT_SECONDARY,
    QPalette.ColorRole.Text: Color.DISABLED,
    QPalette.ColorRole.Button: Color.SURFACE_SUBTLE,
    QPalette.ColorRole.ButtonText: Color.DISABLED,
    QPalette.ColorRole.BrightText: "#ffffff",
    QPalette.ColorRole.Light: Color.SURFACE,
    QPalette.ColorRole.Midlight: Color.SURFACE_SUBTLE,
    QPalette.ColorRole.Dark: Color.BORDER,
    QPalette.ColorRole.Mid: Color.SEPARATOR,
    QPalette.ColorRole.Shadow: Color.TEXT_MUTED,
    QPalette.ColorRole.Highlight: "#e5e9ef",
    QPalette.ColorRole.HighlightedText: Color.TEXT_MUTED,
    QPalette.ColorRole.Link: Color.DISABLED,
    QPalette.ColorRole.LinkVisited: Color.DISABLED,
    QPalette.ColorRole.PlaceholderText: Color.DISABLED,
}


def build_light_palette() -> QPalette:
    """Return a complete light palette independent of the host OS palette."""
    palette = QPalette()
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, value in _ACTIVE_LIGHT_ROLES.items():
            palette.setColor(group, role, QColor(value))
    for role, value in _DISABLED_LIGHT_ROLES.items():
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(value))

    # Qt 6.8+ exposes an Accent palette role.  Keep this conditional so the
    # module remains tolerant of supported PySide6 minor-version differences.
    accent_role = getattr(QPalette.ColorRole, "Accent", None)
    if accent_role is not None:
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            palette.setColor(group, accent_role, QColor(Color.ACCENT))
        palette.setColor(QPalette.ColorGroup.Disabled, accent_role, QColor(Color.DISABLED))
    return palette


def enforce_light_application_appearance(app: QApplication) -> None:
    """Pin Qt to SlopeForge's light appearance before constructing widgets."""
    style_hints = app.styleHints()
    set_color_scheme = getattr(style_hints, "setColorScheme", None)
    if callable(set_color_scheme):
        set_color_scheme(Qt.ColorScheme.Light)
    app.setPalette(build_light_palette())
