from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMenu, QPushButton, QWidget

from database.app_context import AppContext
from ui.settings_dialog import SettingsDialog


class Header(QWidget):
<<<<<<< HEAD
    create_project_requested = Signal()
    create_block_requested = Signal()
    directories_requested = Signal()
    delete_requested = Signal()
=======
    create_block_requested = Signal()
    directories_requested = Signal()
>>>>>>> origin/main

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

<<<<<<< HEAD
        self.create_project = QPushButton("Create project")
        self.create_project.clicked.connect(self.directories_requested.emit)
        self.create_project.setEnabled(context.current_user.can_edit)

        self.add_button = QPushButton("Add ▼")
        menu = QMenu(self)
        mine_action = menu.addAction("Mine")
        site_action = menu.addAction("Site")
        block_action = menu.addAction("Blast block")
=======
        self.add_button = QPushButton("Add ▼")
        menu = QMenu(self)
        mine_action = menu.addAction("Add mine")
        site_action = menu.addAction("Add site")
        block_action = menu.addAction("Add blast block")
>>>>>>> origin/main
        mine_action.triggered.connect(self.directories_requested.emit)
        site_action.triggered.connect(self.directories_requested.emit)
        block_action.triggered.connect(self.create_block_requested.emit)
        self.add_button.setMenu(menu)
        self.add_button.setEnabled(context.current_user.can_edit)

<<<<<<< HEAD
        self.delete_button = QPushButton("Delete")
        self.delete_button.setEnabled(False)
        self.delete_button.setToolTip("Delete will be added later")

=======
>>>>>>> origin/main
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (Ctrl+F)")
        self.search.setMaximumWidth(350)

<<<<<<< HEAD
        self.settings = QPushButton("Settings")
        self.settings.clicked.connect(self.open_settings)

        layout.addWidget(self.create_project)
        layout.addWidget(self.add_button)
        layout.addWidget(self.delete_button)
        layout.addStretch()
        layout.addWidget(self.search)
        layout.addStretch()
        layout.addWidget(self.settings)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.context, self)
=======
        self.export = QPushButton("Export")
        self.settings = QPushButton("Settings")
        self.settings.clicked.connect(self.open_settings)

        layout.addWidget(self.add_button)
        layout.addWidget(self.search)
        layout.addStretch()
        layout.addWidget(self.export)
        layout.addWidget(self.settings)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
>>>>>>> origin/main
        dialog.exec()
