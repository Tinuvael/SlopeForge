from __future__ import annotations

import logging

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from .config import APP_ICON_PATH
from .resources import resource_path

logger = logging.getLogger(__name__)


def application_icon() -> QIcon:
    icon_path = resource_path(APP_ICON_PATH)
    if icon_path is None:
        return QIcon()
    icon = QIcon(str(icon_path))
    if icon.isNull():
        logger.warning("Application icon could not be loaded: %s", icon_path)
    return icon


def apply_application_icon(app: QApplication) -> QIcon:
    icon = application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    return icon


def apply_window_icon(widget: QWidget) -> None:
    icon = QApplication.windowIcon()
    if not icon.isNull():
        widget.setWindowIcon(icon)
