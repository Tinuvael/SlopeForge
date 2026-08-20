"""Small UI adapter for the wall-survey RMS service."""
from PySide6.QtWidgets import QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.localization import tr
from infrastructure.geometry_import.wall_rms import calculate_wall_rms_from_csv


class WallRmsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle(tr("Calculate from survey")); self.result = None
        layout = QVBoxLayout(self); form = QFormLayout(); self.design = QLineEdit(); self.survey = QLineEdit()
        form.addRow(tr("Design surface"), self._file_row(self.design)); form.addRow(tr("Actual survey"), self._file_row(self.survey)); layout.addLayout(form)
        self.statistics = QLabel(tr("Load both CSV files, then calculate.")); layout.addWidget(self.statistics)
        buttons = QHBoxLayout(); calculate = QPushButton(tr("Calculate")); self.use = QPushButton(tr("Use result")); self.use.setEnabled(False)
        calculate.clicked.connect(self._calculate); self.use.clicked.connect(self.accept); buttons.addStretch(); buttons.addWidget(calculate); buttons.addWidget(self.use); layout.addLayout(buttons)

    def _file_row(self, target):
        host = QWidget(); row = QHBoxLayout(host); row.setContentsMargins(0, 0, 0, 0); row.addWidget(target)
        load = QPushButton(tr("Load…")); load.clicked.connect(lambda: self._load(target)); row.addWidget(load); return host

    def _load(self, target):
        path, _ = QFileDialog.getOpenFileName(self, tr("Load CSV"), "", tr("CSV files (*.csv)"))
        if path: target.setText(path)

    def _calculate(self):
        try:
            self.result = calculate_wall_rms_from_csv(self.design.text(), self.survey.text())
        except Exception as exc:
            QMessageBox.warning(self, tr("Calculation failed"), str(exc)); return
        r = self.result
        self.statistics.setText(f"{tr('Point count')}: {r.point_count}   RMS: {r.rms_m:.3f} m\n{tr('Mean distance')}: {r.mean_m:.3f} m   {tr('Standard deviation')}: {r.std_m:.3f} m\n{tr('Maximum distance')}: {r.max_m:.3f} m   {tr('Minimum distance')}: {r.min_m:.3f} m")
        self.use.setEnabled(True)
