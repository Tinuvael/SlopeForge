from __future__ import annotations
from pathlib import Path
from PySide6.QtGui import QIcon

ICON_ROOT = Path(__file__).resolve().parent / "icons" / "ui"


def ui_icon(name: str, variant: str = "neutral") -> QIcon:
    """Load a SlopeForge UI SVG icon.

    variant: neutral | blue | semantic
    """
    path = ICON_ROOT / "svg" / variant / f"{name}.svg"
    if not path.exists():
        raise FileNotFoundError(f"Unknown SlopeForge icon: {variant}/{name}")
    return QIcon(str(path))
