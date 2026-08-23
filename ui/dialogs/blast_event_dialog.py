from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog,
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QWidget,
)

from app.localization import tr
from application.services.blast_events import BlastEventService, BlastEventValidationError
from application.state.assessment_domain_state import AssessmentDomainState
from ui.presentation_labels import domain_message
from ui.widgets.design_system import (
    ChevronDoubleSpinBox, configure_standard_dialog, create_form_section,
    set_button_role, standard_dialog_actions,
)


GEOMETRY_FILE_FILTER = (
    "Geometry files (*.dxf *.dm *.dmx);;AutoCAD DXF (*.dxf);;Datamine files (*.dm *.dmx)"
)
DRILLHOLE_FILE_FILTER = (
    "Drillhole files (*.dxf *.dm *.dmx);;AutoCAD DXF (*.dxf);;Datamine files (*.dm *.dmx)"
)


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
        layout = configure_standard_dialog(self, minimum_width=580)
        general, form = create_form_section("General", self)
        self.name = QLineEdit()
        self.name.textEdited.connect(self._name_edited)
        self.kind = QComboBox()
        self.kind.addItem(tr("Production"), "production")
        self.kind.addItem(tr("Contour blast"), "contour")
        self.has_date = QCheckBox(tr("Set planned date"))
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setEnabled(False)
        self.has_date.toggled.connect(self.date.setEnabled)
        form.addRow(tr("Title *"), self.name)
        form.addRow(tr("Type *"), self.kind)
        date_row = QHBoxLayout()
        date_row.setContentsMargins(0, 0, 0, 0)
        date_row.addWidget(self.has_date)
        date_row.addWidget(self.date, 1)
        form.addRow(tr("Planned blast date"), date_row)
        layout.addWidget(general)

        geometry, geometry_form = create_form_section("Geometry", self)
        self.csv = QLineEdit()
        self.browse_button = set_button_role(QPushButton(tr("Browse...")), "secondary")
        self.browse_button.clicked.connect(self._choose_csv)
        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.addWidget(self.csv, 1)
        file_row.addWidget(self.browse_button)
        self.geometry_file_label = QLabel()

        self.design_drillholes = QLineEdit()
        self.design_drillholes.setPlaceholderText(tr("Optional — can be imported later"))
        self.design_drillholes.setReadOnly(True)
        self.design_drillholes_browse = set_button_role(
            QPushButton(tr("Browse...")), "secondary"
        )
        self.design_drillholes_browse.clicked.connect(self._choose_design_drillholes)
        self.design_drillholes_host = QWidget()
        drillhole_row = QHBoxLayout(self.design_drillholes_host)
        drillhole_row.setContentsMargins(0, 0, 0, 0)
        drillhole_row.addWidget(self.design_drillholes, 1)
        drillhole_row.addWidget(self.design_drillholes_browse)

        self.elevation = ChevronDoubleSpinBox()
        self.elevation.setRange(-10000, 10000)
        self.elevation.setDecimals(0)
        self.elevation.setSingleStep(1)
        self.elevation.valueChanged.connect(self._elevation_changed)
        self.detect_button = set_button_role(QPushButton(tr("Detect automatically")), "secondary")
        self.detect_button.clicked.connect(self._auto_detect)
        elevation_row = QHBoxLayout()
        elevation_row.setContentsMargins(0, 0, 0, 0)
        elevation_row.addWidget(self.elevation, 1)
        elevation_row.addWidget(self.detect_button)
        geometry_form.addRow(self.geometry_file_label, file_row)
        geometry_form.addRow(tr("Design drillholes"), self.design_drillholes_host)
        geometry_form.addRow(tr("Horizon, m *"), elevation_row)
        self.geometry_form = geometry_form
        self.auto_status = QLabel(tr("Select a geometry file to detect the horizon automatically"))
        self.auto_status.setObjectName("FormHelperText")
        self.auto_status.setWordWrap(True)
        geometry.layout.addWidget(self.auto_status)
        layout.addWidget(geometry)
        actions, self.cancel_button, self.create_button = standard_dialog_actions(
            self, "Create", accept=self._validate_and_accept,
        )
        self.buttons = actions
        layout.addWidget(actions)
        self.kind.currentIndexChanged.connect(self._event_type_changed)
        self._sync_drillhole_row()
        self.name.setFocus()

    def _choose_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select geometry file"),
            "",
            tr(GEOMETRY_FILE_FILTER),
        )
        if not path:
            return
        self.csv.setText(path)
        self.csv.setToolTip(path)
        if not self.name_is_manual:
            self._applying_name = True; self.name.setText(Path(path).stem); self._applying_name = False
        self._inspect(force_override=True)

    def _choose_design_drillholes(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select design drillholes"),
            "",
            tr(DRILLHOLE_FILE_FILTER),
        )
        if path:
            self.design_drillholes.setText(path)
            self.design_drillholes.setToolTip(path)

    def _name_edited(self, _text):
        if not self._applying_name:
            self.name_is_manual = True

    def _event_type_changed(self, _event_type):
        self._sync_drillhole_row()
        if self.csv.text().strip():
            self._inspect(force_override=True)

    def _sync_drillhole_row(self):
        is_production = self.kind.currentData() == "production"
        self.geometry_form.setRowVisible(self.design_drillholes_host, is_production)
        if is_production:
            self.geometry_file_label.setText(tr("Block upper contour *"))
            self.csv.setPlaceholderText(tr("Select the block upper contour"))
        else:
            self.geometry_file_label.setText(tr("Contour drillholes *"))
            self.csv.setPlaceholderText(tr("Select contour drillholes"))
            self.design_drillholes.clear()
            self.design_drillholes.setToolTip("")

    def _auto_detect(self):
        self._inspect(force_override=True)

    def _inspect(self, *, force_override):
        path = self.csv.text().strip()
        if not path:
            self.auto_status.setText(tr("Select a geometry file first")); return False
        try:
            preview = self.service.inspect_event_geometry(self.kind.currentData(), path)
        except BlastEventValidationError as exc:
            self.preview = None
            self.auto_status.setText(
                tr("Automatic detection failed: %1").replace("%1", domain_message(str(exc)))
            )
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
        return {
            "name": self.name.text(),
            "event_type": self.kind.currentData(),
            "event_date": self.date.date().toPython() if self.has_date.isChecked() else None,
            "elevation": self.elevation.value(),
            "csv_path": self.csv.text(),
            "design_drillhole_path": self.design_drillholes.text().strip() or None,
        }
