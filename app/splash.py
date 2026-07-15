from __future__ import annotations

import logging

from PySide6.QtCore import QElapsedTimer, QThread, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from .config import APP_AUTHOR, APP_NAME, APP_SPLASH_PATH, APP_VERSION
from .qt import apply_window_icon
from .resources import resource_path

logger = logging.getLogger(__name__)


class SlopeForgeSplash(QSplashScreen):
    def __init__(self) -> None:
        pixmap = self._load_pixmap()
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        apply_window_icon(self)
        self._status = ""
        self._timer = QElapsedTimer()
        self._timer.start()
        self.setFont(QFont("Segoe UI", 10))

    def _load_pixmap(self) -> QPixmap:
        splash_path = resource_path(APP_SPLASH_PATH)
        if splash_path is not None:
            pixmap = QPixmap(str(splash_path))
            if not pixmap.isNull():
                return pixmap.scaled(512, 512, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logger.warning("Splash image could not be loaded: %s", splash_path)
        fallback = QPixmap(512, 512)
        fallback.fill(QColor("white"))
        return fallback

    def show_status(self, message: str) -> None:
        self._status = message
        self.showMessage(message, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, QColor("white"))
        QApplication.processEvents()

    def drawContents(self, painter: QPainter) -> None:  # noqa: N802 - Qt override
        super().drawContents(painter)
        rect = self.rect()
        painter.fillRect(0, rect.height() - 96, rect.width(), 96, QColor(0, 0, 0, 185))
        painter.setPen(QColor("white"))
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(14, rect.height() - 68, APP_NAME)
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(14, rect.height() - 43, f"version {APP_VERSION}")
        painter.drawText(14, rect.height() - 20, APP_AUTHOR)
        if self._status:
            painter.setPen(QColor("#d8eefc"))
            painter.drawText(rect.width() - 250, rect.height() - 20, 236, 18, Qt.AlignmentFlag.AlignRight, self._status)

    def close_with_fade(self, minimum_ms: int = 1000, fade_ms: int = 350) -> None:
        while self._timer.elapsed() < minimum_ms:
            QApplication.processEvents()
            QThread.msleep(20)
        steps = max(1, int(fade_ms / 25))
        for step in range(steps, -1, -1):
            self.setWindowOpacity(step / steps)
            QApplication.processEvents()
            QThread.msleep(max(1, int(fade_ms / steps)))
        self.close()
