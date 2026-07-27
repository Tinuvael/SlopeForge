from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QMainWindow

from app.qt import apply_window_icon
from .prototype_page import Prototype2DPage


class Prototype2DWindow(QMainWindow):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Прототип 2D-плана Datamine")
        self.setMinimumSize(1000, 700)
        self.resize(1300, 850)
        apply_window_icon(self)
        self.page = Prototype2DPage(self)
        self.page.close_requested.connect(self.close)
        self.setCentralWidget(self.page)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
