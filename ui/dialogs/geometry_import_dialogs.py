
from app.localization import tr
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QDialogButtonBox

from infrastructure.geometry_import.csv import FIELD_LABELS, LOGICAL_FIELDS, detect_columns


class ColumnMappingDialog(QDialog):
    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Datamine column mapping"))
        self._combos = {}
        detected = detect_columns(headers)
        layout = QFormLayout(self)
        for field in LOGICAL_FIELDS:
            combo = QComboBox()
            combo.addItem("")
            combo.addItems(headers)
            if detected.get(field):
                combo.setCurrentText(detected[field])
            self._combos[field] = combo
            layout.addRow(FIELD_LABELS[field], combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def mapping(self):
        return {field: combo.currentText() for field, combo in self._combos.items() if combo.currentText()}
