"""Machine-local SlopeForge appearance preference."""
from __future__ import annotations

from PySide6.QtCore import QSettings

from app.localization import settings

THEME_KEY = "ui/theme"
SUPPORTED_THEMES = ("system", "light", "dark")


def normalize_theme(value: object) -> str:
    theme = str(value or "system").lower()
    return theme if theme in SUPPORTED_THEMES else "system"


def selected_theme(store: QSettings | None = None) -> str:
    return normalize_theme((store or settings()).value(THEME_KEY, "system"))


def save_theme(theme: str, store: QSettings | None = None) -> str:
    normalized = normalize_theme(theme)
    target = store or settings()
    target.setValue(THEME_KEY, normalized)
    target.sync()
    return normalized
