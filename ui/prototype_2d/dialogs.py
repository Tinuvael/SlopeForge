from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QDialogButtonBox

from prototype_2d.csv_importer import REQUIRED_FIELDS, OPTIONAL_FIELDS, detect_columns


class ColumnMappingDialog(QDialog):
    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent); self.setWindowTitle("Сопоставление колонок Datamine")
        self._combos = {}; detected = detect_columns(headers)
        layout = QFormLayout(self)
        for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
            combo = QComboBox(); combo.addItem(""); combo.addItems(headers)
            if detected.get(field): combo.setCurrentText(detected[field])
            self._combos[field] = combo; layout.addRow(field, combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def mapping(self):
        return {field: combo.currentText() for field, combo in self._combos.items() if combo.currentText()}
