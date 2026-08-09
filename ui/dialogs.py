
from app.localization import tr
from PySide6.QtWidgets import QDialog


class SettingsDialog(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(tr("Settings"))
        self.resize(850, 550)
