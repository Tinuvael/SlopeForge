from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from app.localization import tr
from application.services.blast_events import BlastEventService, BlastEventValidationError
from application.state.assessment_domain_state import AssessmentDomainState
from ui.presentation_labels import domain_message


class BlastEventDialog(QDialog):
    """Existing production/contour Blast Event input dialog, now independently reusable."""

    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        self.service = service or BlastEventService(AssessmentDomainState())
        self._applying_suggestion = False
        self._applying_name = False
        self.name_is_manual = False
        self.elevation_is_manual = False
        self.preview = None
        self.setWindowTitle(tr("Create Blast Event"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(); self.name.textEdited.connect(self._name_edited)
        self.kind = QComboBox(); self.kind.addItems(["production", "contour"])
        self.has_date = QCheckBox(tr("Set planned date"))
        self.date = QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True); self.date.setEnabled(False)
        self.has_date.toggled.connect(self.date.setEnabled)
        self.elevation = QDoubleSpinBox(); self.elevation.setRange(-10000, 10000)
        self.elevation.setDecimals(0); self.elevation.setSingleStep(1)
        self.elevation.valueChanged.connect(self._elevation_changed)
        self.csv = QLineEdit()
        browse = QPushButton(tr("Select geometry file")); browse.clicked.connect(self._choose_csv)
        file_row = QHBoxLayout(); file_row.addWidget(self.csv); file_row.addWidget(browse)
        auto = QPushButton(tr("Detect automatically")); auto.clicked.connect(self._auto_detect)
        elevation_row = QHBoxLayout(); elevation_row.addWidget(self.elevation); elevation_row.addWidget(auto)
        self.auto_status = QLabel(tr("Select a geometry file to detect the horizon automatically"))
        self.auto_status.setWordWrap(True)
        form.addRow(tr("Title *"), self.name); form.addRow(tr("Type *"), self.kind)
        date_row = QHBoxLayout(); date_row.addWidget(self.has_date); date_row.addWidget(self.date)
        form.addRow(tr("Planned blast date"), date_row); form.addRow(tr("Horizon *"), elevation_row)
        form.addRow(tr("Geometry file *"), file_row); form.addRow("", self.auto_status)
        layout.addLayout(form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("Save"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))
        self.buttons.accepted.connect(self._validate_and_accept); self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.kind.currentTextChanged.connect(self._event_type_changed)

    def _choose_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Select geometry file"), "", tr("Geometry files (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"))
        if not path:
            return
        self.csv.setText(path)
        if not self.name_is_manual:
            self._applying_name = True; self.name.setText(Path(path).stem); self._applying_name = False
        self._inspect(force_override=True)

    def _name_edited(self, _text):
        if not self._applying_name:
            self.name_is_manual = True

    def _event_type_changed(self, _event_type):
        if self.csv.text().strip():
            self._inspect(force_override=True)

    def _auto_detect(self):
        self._inspect(force_override=True)

    def _inspect(self, *, force_override):
        path = self.csv.text().strip()
        if not path:
            self.auto_status.setText(tr("Select a geometry file first")); return False
        try:
            preview = self.service.inspect_event_geometry(self.kind.currentText(), path)
        except BlastEventValidationError as exc:
            self.preview = None
            self.auto_status.setText(f"Automatic detection failed: {domain_message(str(exc))}")
            QMessageBox.warning(self, tr("Automatic horizon detection"), domain_message(str(exc)))
            return False
        self.preview = preview
        if force_override or not self.elevation_is_manual:
            self._applying_suggestion = True
            rounded = int(Decimal(str(preview.suggested_elevation)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            self.elevation.setValue(rounded); self._applying_suggestion = False
            self.elevation_is_manual = False
        if preview.geometry_type == "Polygon":
            text = f"Automatic detection: horizon {self.elevation.value():.0f} from top line SID {preview.selected_source_line_id}"
        else:
            text = (f"Automatic detection: horizon {self.elevation.value():.0f} from median of "
                    f"{preview.accepted_contour_drillhole_count} collars")
            if preview.ignored_flat_contour_line_count:
                text += f"; flat rows excluded: {preview.ignored_flat_contour_line_count}"
        if preview.warning_text:
            text += f"\n{preview.warning_text}"
        self.auto_status.setText(text)
        return True

    def _elevation_changed(self, _value):
        if self._applying_suggestion:
            return
        self.elevation_is_manual = True
        if self.csv.text().strip():
            self.auto_status.setText(tr("Horizon changed manually"))

    def _validate_and_accept(self):
        manual = self.elevation_is_manual
        if not self._inspect(force_override=not manual):
            return
        if manual:
            self.elevation_is_manual = True; self.auto_status.setText(tr("Horizon changed manually"))
        self.accept()

    def values(self):
        return {"name": self.name.text(), "event_type": self.kind.currentText(),
                "event_date": self.date.date().toPython() if self.has_date.isChecked() else None, "elevation": self.elevation.value(),
                "csv_path": self.csv.text()}
