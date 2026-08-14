from app.localization import tr
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)


class RenameEntityDialog(QDialog):
    """Compact Name-only editor shared by Project and Domain dashboards."""

    def __init__(self, entity: str, current_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit Project") if entity == "Project" else tr("Edit Domain"))
        self.setMinimumWidth(360)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(tr("Name")))
        self.name = QLineEdit(current_name)
        self.name.setMaxLength(255)
        self.name.selectAll()
        root.addWidget(self.name)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color:#B91C1C")
        self.error_label.hide()
        root.addWidget(self.error_label)
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = QPushButton(tr("Cancel"))
        self.save_button = QPushButton(tr("Save"))
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)
        root.addLayout(actions)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._validate)

    def _validate(self):
        name = self.name.text().strip()
        if not name:
            self.show_error(tr("Name is required"))
            return
        self.name.setText(name)
        self.error_label.hide()
        self.accept()

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()
        self.name.setFocus()
