from PySide6.QtCore import Qt
from ui.settings_dialog import SettingsDialog
from ui.add_dialog import AddDialog
from database import get_legacy_database
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QPushButton,
    QLineEdit,
    QHBoxLayout,
    QMenu,
    QMessageBox,
)


class Header(QWidget):

    def __init__(self):
        super().__init__()

        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        #
        # Add
        #

        self.add_button = QPushButton("Add ▼")

        menu = QMenu(self)

        for item in (
            "Deposit",
            "Domain",
            "Bench",
            "Block",
        ):

            action = menu.addAction(f"Add {item}")
            action.triggered.connect(
                lambda checked=False, name=item: self.add_item(name)
            )


        self.add_button.setMenu(menu)

        #
        # Search
        #

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (Ctrl+F)")
        self.search.setMaximumWidth(350)

        #
        # Export
        #

        self.export = QPushButton("Export")
        self.export.clicked.connect(lambda: self.clicked("Export"))

        #
        # Settings
        #

        self.settings = QPushButton("Settings")
        self.settings.clicked.connect(self.open_settings)

        layout.addWidget(self.add_button)
        layout.addWidget(self.search)

        layout.addStretch()

        layout.addWidget(self.export)
        layout.addWidget(self.settings)


        

    def open_settings(self):

        dialog = SettingsDialog()

        dialog.exec()


    def add_item(self, item_type):

        dialog = AddDialog(item_type)

        if dialog.exec():

            if item_type == "Deposit":

                get_legacy_database().add_deposit(
                    dialog.name.text(),
                    dialog.description.toPlainText()
                )

                print("Deposit created")

