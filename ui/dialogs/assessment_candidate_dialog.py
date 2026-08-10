from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.localization import tr
from application.services.assessment_areas import AssessmentAreaService
from ui.presentation_labels import domain_message


class AssessmentCandidateDialog(QDialog):
    """Collect the name, date and horizon fragments for a drawn Area."""

    def __init__(self, candidates, parent=None):
        super().__init__(parent)
        self.candidates = candidates
        self.setWindowTitle(tr("Confirm Assessment Area horizons"))
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.area_name = QLineEdit()
        self.area_name.setPlaceholderText(tr("For example: Area 600–620"))
        self.area_date = QDateEdit(QDate.currentDate())
        self.area_date.setCalendarPopup(True)
        form.addRow(tr("Title"), self.area_name)
        form.addRow(tr("Assessment date"), self.area_date)
        layout.addLayout(form)
        layout.addWidget(QLabel(tr("Select no more than one fragment per elevation and at least two elevations:")))
        self.table = QTableWidget(len(candidates), 6)
        self.table.setHorizontalHeaderLabels(
            [tr("Include"), tr("Elevation"), tr("SID"), tr("Fragment"), tr("Length"), tr("Points")]
        )
        counts = {}
        for candidate in candidates:
            counts[candidate.elevation] = counts.get(candidate.elevation, 0) + 1
        for row, candidate in enumerate(candidates):
            check = QCheckBox()
            check.setChecked(counts[candidate.elevation] == 1)
            self.table.setCellWidget(row, 0, check)
            values = (f"{candidate.elevation:g}", candidate.source_line_id,
                      str(candidate.fragment_number), f"{candidate.length:.2f}",
                      str(len(candidate.geometry.points)))
            for column, value in enumerate(values, 1):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_checked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_candidates(self):
        return [candidate for row, candidate in enumerate(self.candidates)
                if self.table.cellWidget(row, 0).isChecked()]

    def _accept_checked(self):
        try:
            AssessmentAreaService.validate_selection(self.selected_candidates())
        except ValueError as exc:
            QMessageBox.warning(self, tr("Horizon selection"), domain_message(str(exc)))
            return
        self.accept()
