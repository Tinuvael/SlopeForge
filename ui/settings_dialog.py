from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_AUTHOR, APP_COPYRIGHT, APP_DESCRIPTION, APP_ICON_PATH, APP_NAME, APP_REPOSITORY_URL, APP_VERSION
from app.qt import apply_window_icon
from app.resources import resource_path


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.setWindowTitle("Settings")
        self.resize(850, 550)

        layout = QHBoxLayout(self)
        self.menu = QListWidget()
        self.menu.setFixedWidth(180)
        self.menu.addItems(["General", "Database", "Appearance", "About"])

        self.pages = QStackedWidget()
        self.pages.addWidget(self.page("General settings"))
        self.pages.addWidget(self.page("Database settings"))
        self.pages.addWidget(self.page("Appearance settings"))
        self.pages.addWidget(self.about_page())

        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)
        layout.addWidget(self.menu)
        layout.addWidget(self.pages)

    def page(self, text: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(text))
        layout.addStretch()
        return widget

    def about_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        icon_label = QLabel()
        icon_path = resource_path(APP_ICON_PATH)
        if icon_path is not None:
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(icon_label)
        layout.addWidget(QLabel(f"<b>{APP_NAME}</b>"))
        layout.addWidget(QLabel(f"Version: {APP_VERSION}"))
        layout.addWidget(QLabel(f"Author: {APP_AUTHOR}"))
        description = QLabel(APP_DESCRIPTION)
        description.setWordWrap(True)
        layout.addWidget(description)
        repository = QLabel(f'<a href="{APP_REPOSITORY_URL}">{APP_REPOSITORY_URL}</a>')
        repository.setOpenExternalLinks(True)
        layout.addWidget(repository)
        layout.addWidget(QLabel(APP_COPYRIGHT))
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch()
        return widget
