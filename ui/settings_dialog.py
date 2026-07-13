from PySide6.QtWidgets import (
    QDialog,
    QListWidget,
    QLabel,
    QHBoxLayout,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
)


class SettingsDialog(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Settings")
        self.resize(850, 550)

        layout = QHBoxLayout(self)

        #
        # Left menu
        #

        self.menu = QListWidget()
        self.menu.setFixedWidth(180)

        self.menu.addItems([
            "General",
            "Database",
            "Appearance",
            "About",
        ])

        #
        # Right pages
        #

        self.pages = QStackedWidget()

        self.pages.addWidget(self.page("General Settings"))
        self.pages.addWidget(self.page("Database Settings"))
        self.pages.addWidget(self.page("Appearance Settings"))
        self.pages.addWidget(self.page("SlopeForge\nVersion 0.1.0"))

        self.menu.currentRowChanged.connect(
            self.pages.setCurrentIndex
        )

        self.menu.setCurrentRow(0)

        layout.addWidget(self.menu)
        layout.addWidget(self.pages)

    def page(self, text):

        widget = QWidget()

        layout = QVBoxLayout(widget)

        label = QLabel(text)

        layout.addWidget(label)
        layout.addStretch()

        return widget
