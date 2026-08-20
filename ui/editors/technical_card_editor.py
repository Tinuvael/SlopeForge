"""Scrollable editor for versioned BlastEvent technical cards."""
from __future__ import annotations

from app.localization import tr

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox, QDateEdit, QDialog, QDoubleSpinBox,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QVBoxLayout, QWidget,
    QInputDialog, QSizePolicy, QHeaderView, QMenu, QWidgetAction)

from domain.blasting.technical_card import (BARTON_JA_VALUES, BARTON_JN_VALUES, BARTON_JR_VALUES,
    BARTON_JW_VALUES, CONTOUR_GROUP_TYPES, CONTROLLED_BLASTING_METHODS, PRODUCTION_GROUP_TYPES,
    ActualDrillingGroup, BlastDrillingGroup, DesignSlopeOrientation, GeomechanicalParameters,
    JointSetOrientation)
from domain.geomechanics.kinematic_screening import (Orientation, estimated_joint_friction_angle,
    indicative_cohesion_kpa, planar_screening, q_prime, wedge_screening)
from ui.widgets.borehole_charge_builder import BoreholeChargeBuilder
from ui.presentation_labels import (
    CONTROLLED_BLASTING_LABELS, domain_message, technical_group_label, technical_text,
)
from ui.widgets.design_system import configure_standard_table, set_button_role

BURDEN_LABEL = "Burden / row spacing, m"
BURDEN_TOOLTIP = "Burden. For row patterns, normally the row spacing or distance from the first row to the free face."
SPACING_LABEL = "Hole spacing in row, m"
SPACING_TOOLTIP = "Distance between adjacent holes in a row."
TOE_LABEL = "Last row to design contour, m"


def _number(value, suffix=""):
    widget = QDoubleSpinBox(); widget.setRange(-1_000_000_000, 1_000_000_000); widget.setDecimals(3)
    widget.setSpecialValueText("—"); widget.setValue(value if value is not None else widget.minimum())
    if suffix: widget.setSuffix(f" {suffix}")
    return widget


class _EngineeringSpinBox(QSpinBox):
    """Integer engineering input with a reliable Windows arrow-button hit area.

    Qt stylesheets turn spin boxes into complex styled controls.  On Windows the
    painted up/down arrows can then become offset from the native hit rectangles.
    Geomechanics uses this tiny wrapper so the visible right-side button zone
    always performs the expected step regardless of the active platform style.
    """

    _button_zone_width = 24

    def mousePressEvent(self, event):
        if (self.isEnabled() and event.button() == Qt.MouseButton.LeftButton
                and event.position().x() >= self.width() - self._button_zone_width):
            if event.position().y() < self.height() / 2:
                self.stepUp()
            else:
                self.stepDown()
            event.accept()
            return
        super().mousePressEvent(event)


def _integer_number(value, valid_minimum, valid_maximum, suffix=""):
    """Compact integer engineering input with one sentinel value for an empty draft field."""
    widget = _EngineeringSpinBox()
    widget.setRange(valid_minimum - 1, valid_maximum)
    widget.setSingleStep(1)
    widget.setSpecialValueText("—")
    widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
    widget.setFixedHeight(28)
    valid = value is not None and valid_minimum <= value <= valid_maximum
    widget.setValue(int(round(value)) if valid else widget.minimum())
    if suffix: widget.setSuffix(f" {suffix}")
    return widget


def _rating_combo(value, allowed_values):
    """Barton ratings are catalogue values, not arbitrary floating-point inputs."""
    combo = QComboBox(); combo.addItem("—", None)
    for rating in allowed_values:
        combo.addItem(f"{rating:g}", float(rating))
    if value is not None:
        index = next((i for i in range(1, combo.count()) if abs(combo.itemData(i) - value) <= 1e-9), 0)
        combo.setCurrentIndex(index)
    return combo


class TechnicalCardDialog(QDialog):
    def __init__(self, event, card, revision, save_callback, parent=None, read_only=False, domain_name="",
                 explosive_products=None, charge_presets=None):
        # QDialog already has an event() method used internally by Qt.  Do not
        # shadow it with the BlastEvent model, otherwise showing the dialog
        # fails with: "BlastEvent object is not callable".
        super().__init__(parent); self.blast_event, self.card, self.revision = event, card, revision
        self.save_callback, self.read_only, self.domain_name = save_callback, read_only, domain_name
        self.explosive_products = list(explosive_products or []); self.charge_presets = charge_presets
        self._charge_builders = []
        self.setWindowTitle(f"{tr('Technical Card')} — {event.name}"); self.setMinimumSize(760, 560); self.resize(940, 720)
        root = QVBoxLayout(self); meta = QLabel(f"{tr('BlastEvent ID')}: {event.id}   |   {tr('Geometry revision')}: {revision.geometry_revision_id}")
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); root.addWidget(meta)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self._common_tab()
        if event.event_type == "production": self._geomechanics_tab(); drilling_title = "Drilling and charging"
        else: drilling_title = "Contour drilling"
        self._drilling_tab(drilling_title); self._actual_tab(); self._history_tab()
        buttons = QHBoxLayout(); buttons.addStretch()
        self.draft_button = QPushButton(tr("Save draft")); self.complete_button = QPushButton(tr("Complete")); cancel = QPushButton(tr("Cancel"))
        set_button_role(self.draft_button, "secondary"); set_button_role(self.complete_button, "primary"); set_button_role(cancel, "secondary")
        self.draft_button.clicked.connect(lambda: self._save("draft")); self.complete_button.clicked.connect(lambda: self._save("completed")); cancel.clicked.connect(self.reject)
        for button in (self.draft_button, self.complete_button): button.setEnabled(not read_only)
        buttons.addWidget(self.draft_button); buttons.addWidget(self.complete_button); buttons.addWidget(cancel); root.addLayout(buttons)

    def _scroll_tab(self, title):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget(); page.setObjectName("EngineeringWorkspace"); layout = QVBoxLayout(page); layout.setContentsMargins(12, 12, 12, 12); layout.setSpacing(12); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(page); self.tabs.addTab(scroll, title); return layout

    def _common_tab(self):
        layout = self._scroll_tab(tr("General")); common = self.revision.common_parameters
        identity = QGroupBox(tr("Event and source")); form = QFormLayout(identity)
        form.addRow(tr("BlastEvent ID"), QLabel(self.blast_event.id)); form.addRow(tr("Geometry revision ID"), QLabel(self.revision.geometry_revision_id))
        form.addRow(tr("Source CSV"), QLabel(common.source_csv or "—")); layout.addWidget(identity)
        block = QGroupBox(tr("Block parameters")); form = QFormLayout(block)
        self.block_name = QLineEdit(common.block_name); self.horizon = _number(common.working_horizon, "m"); self.comments = QLineEdit(common.comments)
        form.addRow(tr("Block name"), self.block_name); form.addRow(tr("Working horizon"), self.horizon); form.addRow(tr("Comments"), self.comments); layout.addWidget(block)
        if self.revision.production_parameters:
            p = self.revision.production_parameters; calc = QGroupBox(tr("Calculated values")); f = QFormLayout(calc)
            f.addRow(tr("Drilling area"), QLabel(f"{p.drilling_area_m2.accepted_value:g} m²" if p.drilling_area_m2.accepted_value is not None else "— m²"))
            self.bench_height = _number(p.design_bench_height_m, "m"); self.production_explosive_label=QLabel("— kg" if p.total_explosive_mass_kg is None else f"{p.total_explosive_mass_kg:g} kg")
            f.addRow(tr("Design bench height"), self.bench_height); f.addRow(tr("Explosive mass"), self.production_explosive_label); layout.addWidget(calc)
        else:
            contour = self.revision.contour_parameters; method = QGroupBox(tr("Controlled blasting method")); f = QFormLayout(method)
            self.method = QComboBox(); self.method.addItem(tr("— select —"), "")
            for key in CONTROLLED_BLASTING_METHODS: self.method.addItem(tr(CONTROLLED_BLASTING_LABELS[key]), key)
            self.method.setCurrentIndex(max(0, self.method.findData(contour.controlled_blasting_method)))
            self.method.currentIndexChanged.connect(self._method_changed); f.addRow(tr("Method"), self.method); layout.addWidget(method)

    def _section_title(self, text):
        label = QLabel(tr(text)); label.setObjectName("EngineeringSectionTitle")
        return label

    def _section_panel(self, title, object_name):
        panel = QWidget(); panel.setObjectName(object_name)
        panel_layout = QVBoxLayout(panel); panel_layout.setContentsMargins(12, 10, 12, 10); panel_layout.setSpacing(8)
        panel_layout.addWidget(self._section_title(title))
        return panel, panel_layout

    def _geomechanics_tab(self):
        page = QWidget(); page.setObjectName("geomechanicsWorkspace")
        layout = QGridLayout(page); layout.setContentsMargins(12, 12, 12, 12); layout.setHorizontalSpacing(12); layout.setVerticalSpacing(12)
        layout.setColumnStretch(0, 2); layout.setColumnStretch(1, 3)
        layout.setRowStretch(0, 0); layout.setRowStretch(1, 0); layout.setRowStretch(2, 0); layout.setRowStretch(3, 1)
        self.tabs.addTab(page, tr("Geomechanics")); geo = self.revision.geomechanical_parameters

        rock_panel, rock = self._section_panel("Rock mass", "rockMassSection")
        identity = QGridLayout(); identity.setHorizontalSpacing(12); identity.setVerticalSpacing(3)
        self.lithology = QLineEdit(geo.lithology); self.lithology.setMaximumWidth(250)
        self.domain_value = QLabel(self.domain_name or "—"); self.domain_value.setObjectName("geomechanicsDomainValue")
        identity.addWidget(QLabel(tr("Lithology")), 0, 0); identity.addWidget(QLabel(tr("Domain")), 0, 1)
        identity.addWidget(self.lithology, 1, 0); identity.addWidget(self.domain_value, 1, 1)
        self.ucs = _integer_number(geo.ucs_mpa, 0, 1_000_000); self.ucs.setObjectName("rockMassUCS")
        self.ff = _integer_number(geo.ff, 0, 1_000_000); self.ff.setObjectName("rockMassFF")
        self.gsi = _integer_number(geo.gsi, 1, 100); self.gsi.setObjectName("rockMassGSI")
        for column, (label, widget, unit) in enumerate((("UCS", self.ucs, "MPa"), ("FF", self.ff, ""), ("GSI", self.gsi, ""))):
            widget.setFixedWidth(96); identity.addWidget(QLabel(label if label == "FF" else tr(label)), 2, column)
            identity.addWidget(widget, 3, column); identity.addWidget(QLabel(unit), 4, column)
        rock.addLayout(identity)

        joint_panel, joint_section = self._section_panel("Joint / discontinuity sets", "jointSetsSection")
        joint_grid = QGridLayout(); joint_grid.setHorizontalSpacing(10); joint_grid.setVerticalSpacing(4)
        for column, label in enumerate(("Set", "Dip, °", "Dip direction, °")): joint_grid.addWidget(QLabel(tr(label)), 0, column)
        self.joint_set_rows = []
        for index in range(5):
            stored = geo.joint_sets[index] if index < len(geo.joint_sets) else None
            dip = _integer_number(stored.dip_deg if stored else None, 0, 90)
            direction = _integer_number(stored.dip_direction_deg if stored else None, 0, 359)
            dip.setObjectName(f"jointSetDip{index + 1}"); direction.setObjectName(f"jointSetDirection{index + 1}")
            dip.setFixedWidth(96); direction.setFixedWidth(110)
            joint_grid.addWidget(QLabel(f"J{index + 1}"), index + 1, 0); joint_grid.addWidget(dip, index + 1, 1); joint_grid.addWidget(direction, index + 1, 2)
            self.joint_set_rows.append((dip, direction))
        joint_section.addLayout(joint_grid)

        q_panel, q_section = self._section_panel("Q-system / discontinuity strength", "qSystemSection")
        qgrid = QGridLayout(); qgrid.setHorizontalSpacing(12); qgrid.setVerticalSpacing(3)
        self.rqd = _integer_number(geo.rqd_percent, 0, 100, "%"); self.rqd.setObjectName("qSystemRQD")
        self.jn = _rating_combo(geo.jn, BARTON_JN_VALUES); self.jn.setObjectName("qSystemJn")
        self.jr = _rating_combo(geo.jr, BARTON_JR_VALUES); self.jr.setObjectName("qSystemJr")
        self.ja = _rating_combo(geo.ja, BARTON_JA_VALUES); self.ja.setObjectName("qSystemJa")
        self.jw = _rating_combo(geo.jw, BARTON_JW_VALUES); self.jw.setObjectName("qSystemJw")
        jw_help_text = tr("Reference parameter — not used in Q′ or structural screening")
        for column, (label, widget) in enumerate((("RQD", self.rqd), ("Jn", self.jn), ("Jr", self.jr), ("Ja", self.ja), ("Jw", self.jw))):
            widget.setFixedWidth(88)
            if label == "Jw":
                header = QWidget(); header_row = QHBoxLayout(header); header_row.setContentsMargins(0, 0, 0, 0); header_row.setSpacing(4)
                jw_label = QLabel("Jw"); jw_label.setToolTip(jw_help_text); header_row.addWidget(jw_label)
                self.jw_help_button = QToolButton(); self.jw_help_button.setText("?"); self.jw_help_button.setAutoRaise(True); self.jw_help_button.setToolTip(jw_help_text)
                header_row.addWidget(self.jw_help_button); header_row.addStretch(); qgrid.addWidget(header, 0, column)
            else:
                qgrid.addWidget(QLabel(label), 0, column)
            qgrid.addWidget(widget, 1, column)
        q_section.addLayout(qgrid)
        values = QHBoxLayout(); self.q_prime_value = QLabel("—"); self.friction_value = QLabel("—"); self.cohesion_value = QLabel("—")
        for label, value in (("Q′", self.q_prime_value), ("Estimated joint friction angle", self.friction_value), ("Indicative cohesion", self.cohesion_value)):
            column = QVBoxLayout(); column.setSpacing(2); caption = QLabel(tr(label)); caption.setObjectName("CalculatedCaption"); value.setObjectName("CalculatedValue")
            column.addWidget(caption); column.addWidget(value); values.addLayout(column); values.addStretch()
        q_section.addLayout(values)

        screening_panel, screening = self._section_panel("Structural screening", "structuralScreeningSection")
        slope_row = QHBoxLayout(); slope_row.addWidget(QLabel(tr("Design slope"))); self.design_slope_value = QLabel("—"); self.design_slope_value.setObjectName("designSlopeReadOnly")
        slope_row.addWidget(self.design_slope_value); slope_row.addStretch(); screening.addLayout(slope_row)
        summaries = QGridLayout(); self.planar_status = QLabel(tr("Incomplete")); self.planar_sets = QLabel(""); self.wedge_status = QLabel(tr("Incomplete")); self.wedge_pairs = QLabel("")
        summaries.setHorizontalSpacing(32)
        summaries.addWidget(QLabel(tr("Planar sliding")), 0, 0); summaries.addWidget(QLabel(tr("Wedge sliding")), 0, 1)
        summaries.addWidget(self.planar_status, 1, 0); summaries.addWidget(self.wedge_status, 1, 1)
        summaries.addWidget(self.planar_sets, 2, 0); summaries.addWidget(self.wedge_pairs, 2, 1); screening.addLayout(summaries)
        details = QPushButton(tr("Details…")); set_button_role(details, "secondary"); details.setMaximumWidth(100); details.clicked.connect(self._show_screening_details); screening.addWidget(details, 0, Qt.AlignmentFlag.AlignRight)
        limitation = QLabel(tr("Preliminary kinematic screening using representative joint-set orientations. Does not account for orientation scatter, persistence, spacing, water pressure or factor of safety.")); limitation.setWordWrap(True); limitation.setObjectName("MutedText"); screening.addWidget(limitation)

        layout.addWidget(rock_panel, 0, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(q_panel, 0, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(joint_panel, 1, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(screening_panel, 1, 1, Qt.AlignmentFlag.AlignTop)

        notes_panel, notes = self._section_panel("Notes", "geomechanicsNotes")
        self.geo_notes = QTextEdit(geo.notes); self.geo_notes.setFixedHeight(58); notes.addWidget(self.geo_notes)
        layout.addWidget(notes_panel, 2, 0, 1, 2, Qt.AlignmentFlag.AlignTop)

        for widget in (self.lithology, self.ucs, self.ff, self.gsi, self.rqd, self.jn, self.jr, self.ja, self.jw): widget.setEnabled(not self.read_only)
        self.geo_notes.setReadOnly(self.read_only)
        for dip, direction in self.joint_set_rows: dip.setEnabled(not self.read_only); direction.setEnabled(not self.read_only)
        self.rqd.valueChanged.connect(self._refresh_geomechanics)
        for combo in (self.jn, self.jr, self.ja): combo.currentIndexChanged.connect(self._refresh_geomechanics)
        for widget in [x for row in self.joint_set_rows for x in row]: widget.valueChanged.connect(self._refresh_geomechanics)
        page.setStyleSheet("""
            #EngineeringSectionTitle { font-weight: 600; color: #1f2937; }
            #EngineeringInlineLabel { font-weight: 600; color: #1f2937; }
            #CalculatedCaption, #MutedText { color: #6b7280; font-size: 11px; }
            #CalculatedValue { color: #0b63ce; font-size: 17px; font-weight: 600; }
            QLineEdit, QTextEdit { min-height: 26px; border: 1px solid #d6dbe3; border-radius: 6px; background: white; padding: 2px 6px; }
            QLineEdit:focus, QTextEdit:focus { border-color: #0b63ce; }
        """)
        self._refresh_geomechanics()

    def _screening_inputs(self):
        joints = []
        for index, (dip, direction) in enumerate(self.joint_set_rows, 1):
            dip_value, direction_value = self._optional_number(dip), self._optional_number(direction)
            if dip_value is not None and direction_value is not None:
                joints.append(Orientation(dip_value, direction_value, f"J{index}"))
        if hasattr(self, "design_slope_azimuth"):
            azimuth, angle = self._optional_number(self.design_slope_azimuth), self._optional_number(self.design_slope_angle)
        else:
            slope = self.revision.design_slope_orientation; azimuth, angle = slope.azimuth_deg, slope.angle_deg
        slope = Orientation(angle, azimuth, "Slope") if angle is not None and azimuth is not None else None
        friction = estimated_joint_friction_angle(self._optional_rating(self.jr), self._optional_rating(self.ja))
        return slope, joints, friction

    def _refresh_geomechanics(self, *_):
        q = q_prime(self._optional_number(self.rqd), self._optional_rating(self.jn), self._optional_rating(self.jr), self._optional_rating(self.ja))
        friction = estimated_joint_friction_angle(self._optional_rating(self.jr), self._optional_rating(self.ja)); cohesion = indicative_cohesion_kpa(friction)
        self.q_prime_value.setText("—" if q is None else f"{q:.2f}"); self.friction_value.setText("—" if friction is None else f"{friction:.1f}°"); self.cohesion_value.setText("—" if cohesion is None else f"{cohesion:.1f} kPa")
        slope, joints, friction = self._screening_inputs(); self._planar_results = []; self._wedge_results = []
        self.design_slope_value.setText("—" if slope is None else f"{slope.dip_direction_deg:g}° / {slope.dip_deg:g}°")
        if slope is None or friction is None:
            self.planar_status.setText(tr("Incomplete")); self.planar_sets.setText(tr("Slope orientation or strength inputs missing")); self.wedge_status.setText(tr("Incomplete")); self.wedge_pairs.setText(tr("Slope orientation or strength inputs missing")); return
        self._planar_results = planar_screening(slope, joints, friction); potentials = [x.joint for x in self._planar_results if x.potential]
        self.planar_status.setText(tr("Potential") if potentials else tr("Not indicated")); self.planar_sets.setText(", ".join(potentials))
        if len(joints) < 2:
            self.wedge_status.setText(tr("Incomplete")); self.wedge_pairs.setText(tr("Insufficient joint sets")); return
        self._wedge_results = wedge_screening(slope, joints, friction); pairs = [f"{x.first} × {x.second}" for x in self._wedge_results if x.potential]
        self.wedge_status.setText(tr("Potential") if pairs else tr("Not indicated")); self.wedge_pairs.setText(", ".join(pairs))
        for status in (self.planar_status, self.wedge_status):
            potential = status.text() == tr("Potential")
            status.setStyleSheet("color: #8a5a00; font-weight: 600;" if potential else "color: #475569; font-weight: 600;")

    def _show_screening_details(self):
        dialog = QDialog(self); dialog.setWindowTitle(tr("Structural screening details")); dialog.resize(900, 420)
        layout = QVBoxLayout(dialog); tabs = QTabWidget(); layout.addWidget(tabs)
        planar = QTableWidget(len(self._planar_results), 7); planar.setHorizontalHeaderLabels([tr(x) for x in ("Set", "Dip / Dip direction", "Δaz", "Δaz <= 20°", "φj < dip", "dip < slope", "Result")])
        for row, result in enumerate(self._planar_results):
            values = (result.joint, f"{result.dip_deg:g}° / {result.dip_direction_deg:g}°", f"{result.azimuth_difference_deg:.1f}°", result.azimuth_pass, result.friction_pass, result.daylight_pass, tr("Potential") if result.potential else tr("Not indicated"))
            for column, value in enumerate(values): planar.setItem(row, column, QTableWidgetItem("✓" if value is True else "✗" if value is False else str(value)))
        wedge = QTableWidget(len(self._wedge_results), 8); wedge.setHorizontalHeaderLabels([tr(x) for x in ("Pair", "Trend", "Plunge", "Criterion 1", "Criterion 2", "Criterion 3", "Plunge > φj", "Result")])
        for row, result in enumerate(self._wedge_results):
            line = result.line; values = (f"{result.first} × {result.second}", "—" if line is None else f"{line.trend_deg:.2f}°", "—" if line is None else f"{line.plunge_deg:.2f}°", *result.criterion_passes, result.friction_pass, tr("Potential") if result.potential else tr("Not indicated"))
            for column, value in enumerate(values): wedge.setItem(row, column,QTableWidgetItem("✓" if value is True else "✗" if value is False else str(value)))
        for table in (planar, wedge): table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tabs.addTab(planar, tr("Planar")); tabs.addTab(wedge, tr("Wedges")); close = QPushButton(tr("Close")); close.clicked.connect(dialog.accept); layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight); dialog.exec()

    @staticmethod
    def _optional_number(widget):
        return None if widget.value() == widget.minimum() else widget.value()

    @staticmethod
    def _optional_rating(widget):
        return widget.currentData()

    def _geomechanics_from_form(self):
        joint_sets = []
        for index, (dip_widget, direction_widget) in enumerate(self.joint_set_rows, start=1):
            dip = self._optional_number(dip_widget); direction = self._optional_number(direction_widget)
            if (dip is None) != (direction is None):
                raise ValueError(f"Joint set {index} requires both dip and dip direction")
            if dip is None:
                continue
            joint_sets.append(JointSetOrientation(dip, direction))
        return GeomechanicalParameters(
            lithology=self.lithology.text(), ucs_mpa=self._optional_number(self.ucs),
            rqd_percent=self._optional_number(self.rqd), gsi=self._optional_number(self.gsi), ff=self._optional_number(self.ff),
            joint_sets=joint_sets, jw=self._optional_rating(self.jw), jn=self._optional_rating(self.jn),
            jr=self._optional_rating(self.jr), ja=self._optional_rating(self.ja), notes=self.geo_notes.toPlainText(),
        )

    def _drilling_tab(self, title):
        self.drilling_layout = self._scroll_tab(tr(title))
        planned = QGroupBox(tr("Blast design")); planned.setObjectName("EngineeringCard"); planned_form = QFormLayout(planned)
        self.has_planned_date = QCheckBox(tr("Set planned date")); self.planned_date = QDateEdit(); self.planned_date.setCalendarPopup(True)
        if self.blast_event.event_date:
            value = self.blast_event.event_date; self.planned_date.setDate(QDate(value.year, value.month, value.day)); self.has_planned_date.setChecked(True)
        else:
            self.planned_date.setDate(QDate.currentDate()); self.planned_date.setEnabled(False)
        self.has_planned_date.toggled.connect(self.planned_date.setEnabled)
        date_row = QHBoxLayout(); date_row.addWidget(self.has_planned_date); date_row.addWidget(self.planned_date)
        planned_form.addRow(tr("Planned blast date"), date_row)
        slope=self.revision.design_slope_orientation
        self.design_slope_azimuth=_integer_number(slope.azimuth_deg, 0, 359); self.design_slope_azimuth.setObjectName("designSlopeAzimuth")
        self.design_slope_angle=_integer_number(slope.angle_deg, 0, 90); self.design_slope_angle.setObjectName("designSlopeAngle")
        for spin in (self.design_slope_azimuth,self.design_slope_angle): spin.setMaximumWidth(160); spin.setEnabled(not self.read_only); spin.valueChanged.connect(self._refresh_geomechanics)
        planned_form.addRow(tr("Design slope azimuth, °"),self.design_slope_azimuth); planned_form.addRow(tr("Design slope angle, °"),self.design_slope_angle)
        self.drilling_layout.addWidget(planned)
        self.group_cards = QWidget(); self.group_cards_layout = QVBoxLayout(self.group_cards)
        self.drilling_layout.addWidget(self.group_cards); self._render_groups()
        self.add_group_combo = QComboBox(); catalogue = PRODUCTION_GROUP_TYPES if self.blast_event.event_type == "production" else CONTOUR_GROUP_TYPES
        self.add_group_combo.addItem(tr("+ Add drilling type"), "")
        for key in catalogue: self.add_group_combo.addItem(technical_group_label(key), key)
        self.add_group_combo.activated.connect(self._add_group); self.drilling_layout.addWidget(self.add_group_combo)

    def _render_groups(self):
        while self.group_cards_layout.count():
            item = self.group_cards_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for group in self.revision.drilling_groups:
            display_name = technical_group_label(group.group_type, group.name)
            box = QGroupBox(); box.setObjectName("drillingGroupCard")
            outer = QVBoxLayout(box)
            group_header = QHBoxLayout()
            group_title = QLabel(display_name); group_title.setObjectName("EngineeringGroupTitle")
            enabled_checkbox = QCheckBox(tr("Enabled")); enabled_checkbox.setObjectName("drillingGroupEnabled")
            enabled_checkbox.setChecked(group.included); enabled_checkbox.setEnabled(not self.read_only)
            group_header.addWidget(group_title); group_header.addStretch(); group_header.addWidget(enabled_checkbox)
            outer.addLayout(group_header)
            identity = QFormLayout(); outer.addLayout(identity)
            name = QLineEdit(display_name); name.setEnabled(not self.read_only); identity.addRow(tr("Title"), name); name.textChanged.connect(lambda value, g=group: setattr(g, "name", value))
            columns=QGridLayout(); columns.setColumnStretch(0,0); columns.setColumnStretch(1,1); box.setProperty("engineeringComposition","left-right")
            pattern = QGroupBox(tr("Drilling design")); pattern.setObjectName("drillingDesignArea"); form = QFormLayout(pattern)
            fields = (("Holes, count", "hole_count", "", True), ("Diameter, mm", "diameter_mm", "", False),
                ("Average depth, m", "average_depth_m", "", False), ("Subdrill, m", "subdrill_m", "", False),
                ("Inclination, °", "inclination_deg", "", False),
                ("Azimuth, °", "azimuth_deg", "", False))
            if self.blast_event.event_type == "production": fields += ((BURDEN_LABEL,"burden_m","",False),(SPACING_LABEL,"spacing_m","",False),("Rows","row_count","",True),(TOE_LABEL,"toe_standoff_m","",False))
            else: fields += (("Design line / collar offset, m","line_offset_m","",False),)
            widgets={}
            for label, attr, suffix, integer in fields: widgets[attr]=self._add_number(form,label,group,attr,suffix,integer,compact=True)
            columns.addWidget(pattern,0,0,Qt.AlignmentFlag.AlignTop)
            charge=QGroupBox(tr("Charge design")); charge.setObjectName("chargeDesignArea"); charge_layout=QVBoxLayout(charge)
            preset_row=QHBoxLayout(); preset_row.addWidget(QLabel(tr("Preset"))); combo=QComboBox(); combo.setObjectName("chargePresetCombo"); combo.setEnabled(not self.read_only); preset_row.addWidget(combo,1)
            load=QPushButton(tr("Load")); save=QPushButton(tr("Save as...")); update=QPushButton(tr("Update")); delete=QPushButton(tr("Delete"))
            for button,name_ in ((load,"loadChargePresetButton"),(save,"saveChargePresetButton"),(update,"updateChargePresetButton"),(delete,"deleteChargePresetButton")):
                button.setObjectName(name_); button.setEnabled(not self.read_only and self.charge_presets is not None); preset_row.addWidget(button)
            for button in (load, save, update): set_button_role(button, "secondary")
            set_button_role(delete, "danger")
            charge_layout.addLayout(preset_row)
            builder_host=QWidget(); builder_layout=QVBoxLayout(builder_host); builder_layout.setContentsMargins(0,0,0,0); charge_layout.addWidget(builder_host,1)
            columns.addWidget(charge,0,1); outer.addLayout(columns)
            summary=QLabel(); summary.setObjectName("drillingChargeSummary"); summary.setWordWrap(True); outer.addWidget(summary)
            state={"builder":None,"last_depth":group.average_depth_m}
            self._refresh_preset_combo(combo)
            def refresh(g=group,label=summary):
                drilling=g.drilling_length(); per=g.explosive_mass_per_hole_kg(); total=g.total_explosive_mass()
                show=lambda value: "—" if value is None else f"{value:.3f}"
                label.setText(f"{tr('Drilling length')}: {show(drilling)} m   |   {tr('Explosive mass / hole')}: {show(per)} kg   |   {tr('Total explosive mass')}: {show(total)} kg")
                if self.revision.production_parameters: self.revision.production_parameters.recalculate(self.revision.drilling_groups)
                if self.revision.production_parameters: self.production_explosive_label.setText(show(self.revision.production_parameters.total_explosive_mass_kg)+" kg")
            def ensure_builder(g=group):
                depth=g.average_depth_m
                if not depth or depth <= 0:
                    if state["builder"]: state["builder"].deleteLater(); state["builder"]=None
                    if not builder_layout.count(): builder_layout.addWidget(QLabel(tr("Enter average hole depth to configure the charge construction.")))
                    return
                while builder_layout.count():
                    item=builder_layout.takeAt(0)
                    if item.widget(): item.widget().deleteLater()
                builder=BoreholeChargeBuilder(depth,g.diameter_mm,self.explosive_products,g.charge_components,self.read_only)
                builder.setObjectName("boreholeChargeBuilder"); builder.setMinimumHeight(350); builder.setMaximumHeight(500)
                builder.components_changed.connect(lambda values,g=g:(setattr(g,"charge_components",values),refresh()))
                builder_layout.addWidget(builder); self._charge_builders.append(builder); state["builder"]=builder; state["last_depth"]=depth
            ensure_builder(); refresh()
            def depth_changed(value,g=group,w=widgets["average_depth_m"]):
                value=None if value==w.minimum() else value
                if state["builder"] and value and not state["builder"].set_hole_depth(value):
                    w.blockSignals(True); w.setValue(state["last_depth"]); w.blockSignals(False); g.average_depth_m=state["last_depth"]; return
                g.average_depth_m=value
                if state["builder"]: state["last_depth"]=value
                else: ensure_builder()
                refresh()
            widgets["average_depth_m"].valueChanged.disconnect(); widgets["average_depth_m"].valueChanged.connect(depth_changed)
            widgets["diameter_mm"].valueChanged.connect(lambda value,w=widgets["diameter_mm"]: state["builder"] and state["builder"].set_hole_diameter(None if value==w.minimum() else value))
            for attr in ("hole_count","diameter_mm","subdrill_m"): widgets[attr].valueChanged.connect(refresh)
            enabled_checkbox.toggled.connect(lambda checked,g=group:(setattr(g,"included",checked),refresh()))
            load.clicked.connect(lambda _=False,c=combo,g=group:self._load_preset(c,g,state,refresh))
            save.clicked.connect(lambda _=False,c=combo,g=group:self._save_preset(c,g))
            update.clicked.connect(lambda _=False,c=combo,g=group:self._update_preset(c,g))
            delete.clicked.connect(lambda _=False,c=combo:self._delete_preset(c))
            actions = QHBoxLayout(); duplicate = QPushButton(tr("Duplicate")); remove = QPushButton(tr("Delete"))
            duplicate.setEnabled(not self.read_only); remove.setEnabled(not self.read_only)
            set_button_role(duplicate, "secondary"); set_button_role(remove, "danger")
            duplicate.clicked.connect(lambda _=False, g=group: self._duplicate(g)); remove.clicked.connect(lambda _=False, g=group: self._remove(g))
            actions.addStretch(); actions.addWidget(duplicate); actions.addWidget(remove); outer.addLayout(actions); self.group_cards_layout.addWidget(box)

    def _add_number(self, form, label, model, attr, suffix="", integer=False,compact=False):
        widget = _number(getattr(model, attr), suffix); widget.setObjectName(attr)
        widget.setEnabled(not self.read_only)
        if compact: widget.setMinimumWidth(120); widget.setMaximumWidth(160); widget.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
        if attr == "burden_m": widget.setToolTip(tr(BURDEN_TOOLTIP))
        if attr == "spacing_m": widget.setToolTip(tr(SPACING_TOOLTIP))
        widget.valueChanged.connect(lambda value, m=model, a=attr, i=integer, w=widget:
            setattr(m, a, None if value == w.minimum() else (int(value) if i else value)))
        form.addRow(tr(label), widget); return widget

    def _refresh_preset_combo(self, combo, selected=None):
        combo.clear()
        if self.charge_presets is None:return
        for preset in self.charge_presets.list_presets(): combo.addItem(preset.name,preset)
        if selected is not None:
            index=next((i for i in range(combo.count()) if combo.itemData(i).id==selected),-1)
            if index>=0: combo.setCurrentIndex(index)

    def _refresh_all_preset_combos(self,selected=None):
        for combo in self.group_cards.findChildren(QComboBox,"chargePresetCombo"): self._refresh_preset_combo(combo,selected)

    def _load_preset(self,combo,group,state,refresh):
        preset=combo.currentData()
        if not preset or not group.average_depth_m:return
        if group.charge_components:
            prompt=QMessageBox(self); prompt.setWindowTitle(tr("Charge preset")); prompt.setText(
                tr('Replace the current charge construction with preset "{name}"?').format(name=preset.name))
            replace=prompt.addButton(tr("Replace"),QMessageBox.ButtonRole.AcceptRole)
            prompt.addButton(QMessageBox.StandardButton.Cancel); prompt.exec()
            if prompt.clickedButton() is not replace:return
        try: values=self.charge_presets.apply(preset,self.explosive_products,group.average_depth_m)
        except Exception as exc: self._show_preset_error(exc); return
        group.charge_components=values
        if state["builder"]: state["builder"].set_components(values)
        refresh()

    def _save_preset(self,combo,group):
        name,ok=QInputDialog.getText(self,tr("Save charge preset"),tr("Preset name"))
        if not ok:return
        try:preset=self.charge_presets.create(name,group.charge_components,self.explosive_products)
        except Exception as exc:self._show_preset_error(exc); return
        self._refresh_all_preset_combos(preset.id)

    def _update_preset(self,combo,group):
        preset=combo.currentData()
        if not preset:return
        if QMessageBox.question(self,tr("Charge preset"),tr('Overwrite Project preset "{name}"?').format(name=preset.name),
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:updated=self.charge_presets.update(preset.id,preset.name,group.charge_components,self.explosive_products)
        except Exception as exc:self._show_preset_error(exc); return
        self._refresh_all_preset_combos(updated.id)

    def _delete_preset(self,combo):
        preset=combo.currentData()
        if not preset:return
        if QMessageBox.question(self,tr("Charge preset"),tr('Delete Project preset "{name}" permanently?').format(name=preset.name),
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:self.charge_presets.delete(preset.id)
        except Exception as exc:self._show_preset_error(exc); return
        self._refresh_all_preset_combos()

    def _show_preset_error(self,exc):
        safe=str(exc) if isinstance(exc,(ValueError,LookupError,PermissionError)) else tr("Could not save the charge preset.")
        QMessageBox.warning(self,tr("Charge preset"),safe)

    def _add_group(self, index):
        kind = self.add_group_combo.itemData(index)
        if not kind: return
        catalogue = PRODUCTION_GROUP_TYPES if self.blast_event.event_type == "production" else CONTOUR_GROUP_TYPES
        group = BlastDrillingGroup(group_type=kind, name=technical_group_label(kind), sequence_order=len(self.revision.drilling_groups)+1)
        if kind == "other": group.custom_type_name = "Other type"
        self.revision.drilling_groups.append(group); self.add_group_combo.setCurrentIndex(0); self._render_groups()

    def _duplicate(self, group):
        from copy import deepcopy
        from uuid import uuid4
        copy = deepcopy(group); copy.id = f"DG-{uuid4().hex}"; copy.name += " (copy)"; copy.sequence_order = len(self.revision.drilling_groups)+1
        self.revision.drilling_groups.append(copy); self._render_groups()

    def _remove(self, group):
        try: self.card.remove_group(self.revision, group.id)
        except ValueError as exc: QMessageBox.warning(self, tr("Delete"), domain_message(str(exc))); return
        self._render_groups()

    def _method_changed(self):
        if self.method.currentData(): self.revision.contour_parameters.set_method(self.method.currentData())

    def _actual_tab(self):
        layout = self._scroll_tab(tr("Execution fact")); actual=self.revision.actual_execution
        top=QHBoxLayout(); top.setSpacing(8); top.addWidget(QLabel(tr("Actual blast date")))
        self.actual_date=QDateEdit(); self.actual_date.setObjectName("actualBlastDate"); self.actual_date.setCalendarPopup(True)
        stored=QDate.fromString(actual.actual_blast_date or "",Qt.DateFormat.ISODate)
        self.actual_date.setDate(stored if stored.isValid() else QDate.currentDate()); self.actual_date.setEnabled(not self.read_only); top.addWidget(self.actual_date)
        copy_all=QPushButton(tr("Copy design to actual")); copy_all.setObjectName("copyProjectToActualButton"); set_button_role(copy_all, "secondary"); copy_all.setEnabled(not self.read_only); copy_all.clicked.connect(self._copy_all_actual); top.addWidget(copy_all)
        self.actual_indicators_button=QPushButton(tr("Actual indicators")); self.actual_indicators_button.setObjectName("actualIndicatorsButton"); set_button_role(self.actual_indicators_button, "secondary"); self.actual_indicators_button.setCheckable(True); self.actual_indicators_button.toggled.connect(self._toggle_actual_indicators); top.addWidget(self.actual_indicators_button); top.addStretch(); layout.addLayout(top)
        self._build_actual_indicators_popup()
        self.completion_status = QComboBox(); planned_status,completed_status="planned","completed"; self.completion_status.addItem(tr("Planned"),planned_status); self.completion_status.addItem(tr("Completed"),completed_status); self.completion_status.setCurrentIndex(max(0,self.completion_status.findData(actual.completion_status))); self.completion_status.hide()
        self.actual_cards=QWidget(); self.actual_cards_layout=QVBoxLayout(self.actual_cards); self.actual_cards_layout.setContentsMargins(0,0,0,0); layout.addWidget(self.actual_cards)
        controls=QHBoxLayout(); add=QPushButton(tr("+ Add actual group")); set_button_role(add, "secondary"); add.setEnabled(not self.read_only); add.clicked.connect(self._add_actual_group); controls.addWidget(add); controls.addStretch(); layout.addLayout(controls)
        notes=QGroupBox(tr("Notes")); notes.setObjectName("EngineeringCard"); notes_layout=QVBoxLayout(notes); self.execution_notes=QTextEdit(actual.execution_notes); self.execution_notes.setObjectName("actualExecutionNotes"); self.execution_notes.setMaximumHeight(76); self.execution_notes.setReadOnly(self.read_only); notes_layout.addWidget(self.execution_notes); layout.addWidget(notes)
        self._render_actual_groups(); self._refresh_actual_summary()

    def _build_actual_indicators_popup(self):
        self.actual_indicators_menu=QMenu(self); self.actual_indicators_menu.setObjectName("actualIndicatorsPopup")
        panel=QWidget(); form=QFormLayout(panel); form.setContentsMargins(12,8,12,8); self.actual_indicator_labels={}
        specs=[("Area, m²","actual_drilling_area_m2"),("Average hole depth, m","actual_average_depth_m"),("Volume, m³","actual_block_volume_m3"),
            ("Total holes","actual_total_hole_count"),("Total drilling length, m","actual_total_drilling_length_m"),("Total explosive mass, kg","actual_total_explosive_mass_kg")]
        if self.blast_event.event_type=="production": specs += [("Rock yield, m³/m","actual_rock_yield_m3_per_drilling_m"),("Powder factor, kg/m³","actual_powder_factor_kg_per_m3")]
        else: specs=specs[3:]
        specs += [("Rejected holes","rejected_hole_count"),("Redrilled holes","redrilled_hole_count"),("Wet holes","wet_hole_count"),("Uncharged holes","uncharged_hole_count")]
        for title,attr in specs:
            value=QLabel("—"); value.setObjectName(f"actualIndicator_{attr}"); value.setAlignment(Qt.AlignmentFlag.AlignRight); form.addRow(tr(title),value); self.actual_indicator_labels[attr]=value
        action=QWidgetAction(self.actual_indicators_menu); action.setDefaultWidget(panel); self.actual_indicators_menu.addAction(action)
        self.actual_indicators_menu.aboutToHide.connect(lambda:self.actual_indicators_button.setChecked(False))

    def _toggle_actual_indicators(self, visible):
        if not visible: self.actual_indicators_menu.hide(); return
        self._refresh_actual_summary(); self.actual_indicators_menu.popup(self.actual_indicators_button.mapToGlobal(self.actual_indicators_button.rect().bottomLeft()))

    def _render_actual_groups(self):
        while self.actual_cards_layout.count():
            item=self.actual_cards_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        designs={g.id:g for g in self.revision.drilling_groups}
        for group in self.revision.actual_execution.actual_drilling_groups:
            design=designs.get(group.design_group_id); display_name=technical_group_label(group.group_type,group.name)
            box=QGroupBox(display_name); box.setObjectName("actualDrillingGroupCard"); box.setCheckable(True); box.setChecked(group.included); box.setEnabled(True)
            outer=QVBoxLayout(box); identity=QFormLayout(); name=QLineEdit(display_name); name.setEnabled(not self.read_only); name.textChanged.connect(lambda value,g=group:setattr(g,"name",value)); identity.addRow(tr("Title"),name); outer.addLayout(identity)
            columns=QGridLayout(); columns.setColumnStretch(0,0); columns.setColumnStretch(1,1); box.setProperty("engineeringComposition","left-right")

            drilling=QGroupBox(tr("Drilling / execution")); drilling.setObjectName("actualDrillingArea")
            field_grid=QGridLayout(drilling); field_grid.setHorizontalSpacing(10); field_grid.setVerticalSpacing(4)
            field_grid.setColumnStretch(0,1); field_grid.setColumnStretch(1,0); field_grid.setColumnStretch(2,0); field_grid.setColumnStretch(3,0)
            headers=((tr("Parameter"),0),(tr("Actual"),1),(tr("Plan"),2),("Δ",3))
            for text,column in headers:
                header=QLabel(text); header.setObjectName("actualComparisonHeader"); header.setStyleSheet("color: #6b7280; font-weight: 600;")
                if column>0: header.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                field_grid.addWidget(header,0,column)

            fields=[("Holes, count","hole_count",True),("Diameter, mm","diameter_mm",False),("Average depth, m","average_depth_m",False),("Subdrill, m","subdrill_m",False),("Inclination, °","inclination_deg",False),("Azimuth, °","azimuth_deg",False)]
            if self.blast_event.event_type=="production": fields += [(BURDEN_LABEL,"burden_m",False),(SPACING_LABEL,"spacing_m",False),("Rows","row_count",True),(TOE_LABEL,"toe_standoff_m",False)]
            else: fields += [("Design line / collar offset, m","line_offset_m",False)]
            state={"builder":None,"depth":group.average_depth_m,"status":None}
            for row_index,(label,attr,integer) in enumerate(fields,1):
                field_grid.addWidget(QLabel(tr(label)),row_index,0)
                widget=_number(getattr(group,attr)); widget.setObjectName(attr); widget.setEnabled(not self.read_only); widget.setMinimumWidth(105); widget.setMaximumWidth(125)
                if integer: widget.setDecimals(0)
                field_grid.addWidget(widget,row_index,1)
                planned=getattr(design,attr) if design else None
                plan_label=QLabel(); plan_label.setObjectName(f"actualPlan_{attr}"); plan_label.setMinimumWidth(58); plan_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter); plan_label.setStyleSheet("color: #6b7280;")
                delta_label=QLabel(); delta_label.setObjectName(f"actualDelta_{attr}"); delta_label.setMinimumWidth(48); delta_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                self._set_comparison_labels(plan_label,delta_label,planned,getattr(group,attr),integer)
                field_grid.addWidget(plan_label,row_index,2); field_grid.addWidget(delta_label,row_index,3)
                def changed(value,g=group,a=attr,w=widget,p=planned,pl=plan_label,dl=delta_label,is_integer=integer,linked=design,st=state):
                    value=None if value==w.minimum() else (int(value) if is_integer else value)
                    builder=st["builder"]
                    if a=="average_depth_m" and builder and value is not None and not builder.set_hole_depth(value):
                        w.blockSignals(True); w.setValue(st["depth"] if st["depth"] is not None else w.minimum()); w.blockSignals(False); return
                    setattr(g,a,value)
                    if a=="average_depth_m": st["depth"]=value
                    if a=="diameter_mm" and builder: builder.set_hole_diameter(value)
                    self._set_comparison_labels(pl,dl,p,value,is_integer)
                    if st["status"] is not None: self._refresh_charge_comparison(st["status"],g,linked)
                    else: self._refresh_actual_summary()
                widget.valueChanged.connect(changed)

            exceptions=QGroupBox(tr("Execution exceptions")); exceptions.setObjectName("actualExceptionArea"); exception_grid=QGridLayout(exceptions); exception_grid.setHorizontalSpacing(10); exception_grid.setVerticalSpacing(4); exception_grid.setColumnStretch(1,1)
            for index,(label,attr) in enumerate((("Rejected","rejected_hole_count"),("Redrilled","redrilled_hole_count"),("Wet","wet_hole_count"),("Uncharged","uncharged_hole_count"))):
                spin=_number(getattr(group,attr)); spin.setDecimals(0); spin.setRange(-1,1000000); spin.setSpecialValueText("—"); spin.setMaximumWidth(90); spin.setEnabled(not self.read_only); spin.valueChanged.connect(lambda value,g=group,a=attr,w=spin:(setattr(g,a,None if value==w.minimum() else int(value)),self._refresh_actual_summary()))
                exception_grid.addWidget(QLabel(tr(label)),index,0); exception_grid.addWidget(spin,index,1,Qt.AlignmentFlag.AlignLeft)
            left=QVBoxLayout(); left.setContentsMargins(0,0,0,0); left.addWidget(drilling); left.addWidget(exceptions); left_host=QWidget(); left_host.setLayout(left); columns.addWidget(left_host,0,0,Qt.AlignmentFlag.AlignTop)

            charge=QGroupBox(tr("Actual charge construction")); charge.setObjectName("actualChargeArea"); charge_layout=QVBoxLayout(charge)
            if group.average_depth_m and group.average_depth_m>0:
                builder=BoreholeChargeBuilder(group.average_depth_m,group.diameter_mm,self.explosive_products,group.charge_components,self.read_only); builder.setObjectName("actualBoreholeChargeBuilder"); builder.setMinimumHeight(350); builder.setMaximumHeight(500); self._charge_builders.append(builder); state["builder"]=builder; charge_layout.addWidget(builder)
                comparison=self._make_charge_comparison(); state["status"]=comparison
                builder.components_changed.connect(lambda values,g=group,d=design,c=comparison:(setattr(g,"charge_components",values),self._refresh_charge_comparison(c,g,d)))
                self._refresh_charge_comparison(comparison,group,design); charge_layout.addWidget(comparison["widget"])
            else: charge_layout.addWidget(QLabel(tr("Enter average hole depth to configure the charge construction.")))
            columns.addWidget(charge,0,1); outer.addLayout(columns)
            actions=QHBoxLayout(); duplicate=QPushButton(tr("Duplicate")); remove=QPushButton(tr("Delete")); set_button_role(duplicate, "secondary"); set_button_role(remove, "danger"); duplicate.setEnabled(not self.read_only); remove.setEnabled(not self.read_only); duplicate.clicked.connect(lambda _=False,g=group:self._duplicate_actual(g)); remove.clicked.connect(lambda _=False,g=group:self._remove_actual(g)); actions.addStretch(); actions.addWidget(duplicate); actions.addWidget(remove); outer.addLayout(actions)
            box.toggled.connect(lambda checked,g=group:(setattr(g,"included",checked),self._refresh_actual_summary())); box.setCheckable(not self.read_only); self.actual_cards_layout.addWidget(box)

    @staticmethod
    def _format_comparison_number(value, integer=False, decimals=3, signed=False):
        if value is None: return "—"
        if integer:
            text=str(int(round(value)))
        else:
            text=f"{float(value):.{decimals}f}".rstrip("0").rstrip(".")
        if signed and value>0: text=f"+{text}"
        return text

    @classmethod
    def _comparison_display(cls, plan, actual, integer=False):
        plan_text=cls._format_comparison_number(plan,integer)
        if plan is None or actual is None: return plan_text,"—",False
        delta=actual-plan
        if abs(delta)<1e-9: return plan_text,"—",False
        return plan_text,cls._format_comparison_number(delta,integer,signed=True),True

    @classmethod
    def _set_comparison_labels(cls, plan_label, delta_label, plan, actual, integer=False):
        plan_text,delta_text,changed=cls._comparison_display(plan,actual,integer)
        plan_label.setText(plan_text); delta_label.setText(delta_text)
        delta_label.setStyleSheet("color: #0b63ce; font-weight: 600;" if changed else "color: #9ca3af;")

    def _make_charge_comparison(self):
        widget=QWidget(); widget.setObjectName("actualChargeComparison"); layout=QVBoxLayout(widget); layout.setContentsMargins(0,4,0,0); layout.setSpacing(4)
        status=QLabel(); status.setObjectName("actualChargeStatus"); layout.addWidget(status)
        grid=QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(3); grid.setColumnStretch(0,1)
        for text,column in ((tr("Plan"),1),(tr("Actual"),2),("Δ",3)):
            header=QLabel(text); header.setObjectName("actualChargeComparisonHeader"); header.setAlignment(Qt.AlignmentFlag.AlignRight); header.setStyleSheet("color: #6b7280; font-weight: 600;"); grid.addWidget(header,0,column)
        rows={}
        for row_index,(title,key) in enumerate(((tr("Mass / hole"),"per"),(tr("Total mass"),"total")),1):
            grid.addWidget(QLabel(title),row_index,0)
            row={}
            for column,name in ((1,"plan"),(2,"actual"),(3,"delta")):
                value=QLabel("—"); value.setObjectName(f"actualCharge_{key}_{name}"); value.setMinimumWidth(72); value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter); grid.addWidget(value,row_index,column); row[name]=value
            rows[key]=row
        layout.addLayout(grid)
        return {"widget":widget,"status":status,"rows":rows}

    @classmethod
    def _set_charge_comparison_row(cls, row, plan, actual):
        row["plan"].setText(cls._format_comparison_number(plan,decimals=1))
        row["actual"].setText(cls._format_comparison_number(actual,decimals=1))
        if plan is None or actual is None or abs(actual-plan)<1e-9:
            row["delta"].setText("—"); row["delta"].setStyleSheet("color: #9ca3af;")
        else:
            row["delta"].setText(cls._format_comparison_number(actual-plan,decimals=1,signed=True)); row["delta"].setStyleSheet("color: #0b63ce; font-weight: 600;")

    def _refresh_charge_comparison(self,comparison,actual,design):
        matches=actual.charge_matches(design) if design else False
        if design is None: comparison["status"].setText(tr("Not in design"))
        else: comparison["status"].setText(tr("Charge matches design") if matches else tr("Charge changed"))
        comparison["status"].setStyleSheet("color: #475569; font-weight: 600;" if matches else "color: #0b63ce; font-weight: 600;")
        plan_per=design.explosive_mass_per_hole_kg() if design else None; fact_per=actual.explosive_mass_per_hole_kg(); plan_total=design.total_explosive_mass() if design else None; fact_total=actual.effective_charge_mass()
        self._set_charge_comparison_row(comparison["rows"]["per"],plan_per,fact_per); self._set_charge_comparison_row(comparison["rows"]["total"],plan_total,fact_total); self._refresh_actual_summary()

    def _copy_all_actual(self):
        actual=self.revision.actual_execution
        if actual.actual_drilling_groups and QMessageBox.question(self,tr("Replace actual with current design?"),tr("Replace actual with current design?"),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        actual.copy_from_design(self.revision.drilling_groups,self.revision.id or None,"replace"); self._render_actual_groups(); self._refresh_actual_summary()

    def _add_actual_group(self):
        catalogue=PRODUCTION_GROUP_TYPES if self.blast_event.event_type=="production" else CONTOUR_GROUP_TYPES; keys=list(catalogue); names=[technical_group_label(key) for key in keys]; choice,ok=QInputDialog.getItem(self,tr("Actual group"),tr("Group type:"),names,0,False)
        if not ok:return
        kind=keys[names.index(choice)]; self.revision.actual_execution.actual_drilling_groups.append(ActualDrillingGroup(design_group_id=None,group_type=kind,name=choice,sequence_order=len(self.revision.actual_execution.actual_drilling_groups)+1)); self._render_actual_groups(); self._refresh_actual_summary()

    def _duplicate_actual(self, group):
        from copy import deepcopy
        from uuid import uuid4
        copied=deepcopy(group); copied.id=f"AG-{uuid4().hex}"; copied.design_group_id=None; copied.copied_from_design=False; copied.copied_from_technical_revision_id=None; copied.copied_at=None; copied.name += " (copy)"; copied.drilling_length_m=None
        self.revision.actual_execution.actual_drilling_groups.append(copied); self._render_actual_groups(); self._refresh_actual_summary()

    def _remove_actual(self, group):
        self.revision.actual_execution.actual_drilling_groups.remove(group); self._render_actual_groups(); self._refresh_actual_summary()

    def _refresh_actual_summary(self):
        actual=self.revision.actual_execution; area=None
        if self.revision.production_parameters: area=self.revision.production_parameters.drilling_area_m2.calculated_value
        actual.recalculate(geometry_area_m2=area,production=self.blast_event.event_type=="production")
        for attr,label in getattr(self,"actual_indicator_labels",{}).items():
            value=getattr(actual,attr); label.setText("—" if value is None else f"{value:g}")

    def set_explosive_products(self, products):
        """Refresh available choices only; builders preserve frozen component snapshots."""
        self.explosive_products=list(products); live=[]
        for builder in self._charge_builders:
            try: builder.set_products(self.explosive_products); live.append(builder)
            except RuntimeError: pass
        self._charge_builders=live

    def _history_tab(self):
        layout = self._scroll_tab(tr("Revision history")); table = QTableWidget(len(self.card.revisions), 5); table.setHorizontalHeaderLabels(["№", tr("Date"), tr("Status"), tr("Geometry revision"), tr("Reason")])
        for row, revision in enumerate(self.card.revisions):
            for col, value in enumerate((revision.revision_number, revision.created_at.isoformat(sep=" ", timespec="minutes"), revision.status, revision.geometry_revision_id, revision.change_reason)): table.setItem(row,col,QTableWidgetItem(str(value)))
        configure_standard_table(table); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.horizontalHeader().setStretchLastSection(True); layout.addWidget(table)

    def _save(self, status):
        if self.read_only:
            QMessageBox.warning(self, tr("Read only"), tr("Archived entities and Viewer accounts cannot change the Technical Card."))
            return False
        self.revision.common_parameters.block_name = self.block_name.text(); self.revision.common_parameters.comments = self.comments.text()
        try:
            self.revision.design_slope_orientation=DesignSlopeOrientation(
                self._optional_number(self.design_slope_azimuth), self._optional_number(self.design_slope_angle))
            if self.revision.production_parameters:
                p=self.revision.production_parameters; p.design_bench_height_m=None if self.bench_height.value()==self.bench_height.minimum() else self.bench_height.value()
                self.revision.geomechanical_parameters = self._geomechanics_from_form()
        except ValueError as exc:
            QMessageBox.warning(self, tr("Technical Card validation"), domain_message(str(exc))); return False
        actual=self.revision.actual_execution; actual.completion_status=self.completion_status.currentData(); actual.actual_blast_date=self.actual_date.date().toString(Qt.DateFormat.ISODate); actual.execution_notes=self.execution_notes.toPlainText(); self._refresh_actual_summary()
        planned_date = self.planned_date.date().toPython() if self.has_planned_date.isChecked() else None
        try: self.save_callback(self.card, self.revision, status, planned_date)
        except ValueError as exc: QMessageBox.warning(self, tr("Technical Card validation"), domain_message(str(exc))); return False
        except Exception as exc:
            QMessageBox.critical(self, tr("Technical Card"), f"Could not save changes. The data remains in the form.\n\n{exc}")
            return False
        self.accept(); return True
