from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.config import APP_AUTHOR, APP_COPYRIGHT, APP_DESCRIPTION, APP_ICON_PATH, APP_NAME, APP_REPOSITORY_URL, APP_VERSION
from app.qt import apply_window_icon
from app.resources import resource_path


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.setFixedWidth(520)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        icon_label = QLabel()
        icon_path = resource_path(APP_ICON_PATH)
        if icon_path is not None:
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        top.addWidget(icon_label)

        text = QVBoxLayout()
        title = QLabel(f"<b>{APP_NAME}</b>")
        version = QLabel(f"Version: {APP_VERSION}")
        author = QLabel(f"Author: {APP_AUTHOR}")
        description = QLabel(APP_DESCRIPTION)
        description.setWordWrap(True)
        repository = QLabel(f'<a href="{APP_REPOSITORY_URL}">{APP_REPOSITORY_URL}</a>')
        repository.setOpenExternalLinks(True)
        copyright_label = QLabel(APP_COPYRIGHT)
        for widget in (title, version, author, description, repository, copyright_label):
            text.addWidget(widget)
        top.addLayout(text)
        layout.addLayout(top)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
