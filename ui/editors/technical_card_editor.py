"""Scrollable editor for versioned BlastEvent technical cards."""
from __future__ import annotations

from app.localization import tr

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QInputDialog, QSizePolicy)

from domain.blasting.technical_card import (CONTOUR_GROUP_TYPES, CONTROLLED_BLASTING_METHODS,
    PRODUCTION_GROUP_TYPES, ActualDrillingGroup, BlastDrillingGroup, DesignSlopeOrientation,
    GeomechanicalParameters, JointSetOrientation)
from ui.widgets.borehole_charge_builder import BoreholeChargeBuilder
from ui.presentation_labels import (
    CONTROLLED_BLASTING_LABELS, domain_message, technical_group_label, technical_text,
)

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


class TechnicalCardDialog(QDialog):
    def __init__(self, event, card, revision, save_callback, parent=None, read_only=False, domain_name="",
                 explosive_products=None, charge_presets=None):
        # QDialog already has an event() method used internally by Qt.  Do not
        # shadow it with the BlastEvent model, otherwise showing the dialog
        # fails with: "BlastEvent object is not callable".
        super().__init__(parent); self.blast_event, self.card, self.revision = event, card, revision
        self.save_callback, self.read_only, self.domain_name = save_callback, read_only, domain_name
        self.explosive_products = list(explosive_products or []); self.charge_presets = charge_presets
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
        self.draft_button.clicked.connect(lambda: self._save("draft")); self.complete_button.clicked.connect(lambda: self._save("completed")); cancel.clicked.connect(self.reject)
        for button in (self.draft_button, self.complete_button): button.setEnabled(not read_only)
        buttons.addWidget(self.draft_button); buttons.addWidget(self.complete_button); buttons.addWidget(cancel); root.addLayout(buttons)

    def _scroll_tab(self, title):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
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

    def _geomechanics_tab(self):
        layout = self._scroll_tab(tr("Geomechanics")); geo = self.revision.geomechanical_parameters
        rock = QGroupBox(tr("Rock mass")); form = QFormLayout(rock)
        self.lithology = QLineEdit(geo.lithology)
        self.domain_value = QLabel(self.domain_name or "—"); self.domain_value.setObjectName("geomechanicsDomainValue")
        self.ucs = _number(geo.ucs_mpa); self.q_value = _number(geo.q_value)
        self.rqd = _number(geo.rqd_percent); self.gsi = _number(geo.gsi); self.jw = _number(geo.jw)
        for widget in (self.lithology, self.ucs, self.q_value, self.rqd, self.gsi, self.jw):
            widget.setEnabled(not self.read_only)
        form.addRow(tr("Lithology"), self.lithology); form.addRow(tr("Domain"), self.domain_value)
        form.addRow(tr("UCS, MPa"), self.ucs); form.addRow(tr("Q"), self.q_value)
        form.addRow(tr("RQD, %"), self.rqd); form.addRow(tr("GSI"), self.gsi); form.addRow(tr("Jw"), self.jw)
        layout.addWidget(rock)

        orientations = QGroupBox(tr("Joint / discontinuity sets")); grid = QGridLayout(orientations)
        grid.addWidget(QLabel(tr("Set")), 0, 0); grid.addWidget(QLabel(tr("Dip, °")), 0, 1)
        grid.addWidget(QLabel(tr("Dip direction, °")), 0, 2)
        self.joint_set_rows = []
        for index in range(5):
            dip = _number(geo.joint_sets[index].dip_deg if index < len(geo.joint_sets) else None)
            direction = _number(geo.joint_sets[index].dip_direction_deg if index < len(geo.joint_sets) else None)
            dip.setObjectName(f"jointSetDip{index + 1}"); direction.setObjectName(f"jointSetDirection{index + 1}")
            dip.setEnabled(not self.read_only); direction.setEnabled(not self.read_only)
            grid.addWidget(QLabel(str(index + 1)), index + 1, 0); grid.addWidget(dip, index + 1, 1)
            grid.addWidget(direction, index + 1, 2); self.joint_set_rows.append((dip, direction))
        layout.addWidget(orientations)

        notes_group = QGroupBox(tr("Notes")); notes_layout = QVBoxLayout(notes_group)
        self.geo_notes = QTextEdit(geo.notes); self.geo_notes.setMaximumHeight(90); self.geo_notes.setReadOnly(self.read_only)
        notes_layout.addWidget(self.geo_notes); layout.addWidget(notes_group)

    @staticmethod
    def _optional_number(widget):
        return None if widget.value() == widget.minimum() else widget.value()

    def _geomechanics_from_form(self):
        joint_sets = []
        for index, (dip_widget, direction_widget) in enumerate(self.joint_set_rows, start=1):
            dip = self._optional_number(dip_widget); direction = self._optional_number(direction_widget)
            if (dip is None) != (direction is None):
                raise ValueError(f"Joint set {index} requires both dip and dip direction")
            if dip is None:
                continue
            if direction == 360:
                direction = 0.0
                direction_widget.setValue(0.0)
            joint_sets.append(JointSetOrientation(dip, direction))
        return GeomechanicalParameters(
            lithology=self.lithology.text(), ucs_mpa=self._optional_number(self.ucs),
            q_value=self._optional_number(self.q_value), rqd_percent=self._optional_number(self.rqd),
            gsi=self._optional_number(self.gsi), joint_sets=joint_sets,
            jw=self._optional_number(self.jw), notes=self.geo_notes.toPlainText(),
        )

    def _drilling_tab(self, title):
        self.drilling_layout = self._scroll_tab(tr(title))
        planned = QGroupBox(tr("Blast design")); planned_form = QFormLayout(planned)
        self.has_planned_date = QCheckBox(tr("Set planned date")); self.planned_date = QDateEdit(); self.planned_date.setCalendarPopup(True)
        if self.blast_event.event_date:
            value = self.blast_event.event_date; self.planned_date.setDate(QDate(value.year, value.month, value.day)); self.has_planned_date.setChecked(True)
        else:
            self.planned_date.setDate(QDate.currentDate()); self.planned_date.setEnabled(False)
        self.has_planned_date.toggled.connect(self.planned_date.setEnabled)
        date_row = QHBoxLayout(); date_row.addWidget(self.has_planned_date); date_row.addWidget(self.planned_date)
        planned_form.addRow(tr("Planned blast date"), date_row)
        slope=self.revision.design_slope_orientation
        self.design_slope_azimuth=_number(slope.azimuth_deg); self.design_slope_azimuth.setRange(-1,360); self.design_slope_azimuth.setSpecialValueText("—"); self.design_slope_azimuth.setObjectName("designSlopeAzimuth")
        self.design_slope_angle=_number(slope.angle_deg); self.design_slope_angle.setRange(-1,90); self.design_slope_angle.setSpecialValueText("—"); self.design_slope_angle.setObjectName("designSlopeAngle")
        for spin in (self.design_slope_azimuth,self.design_slope_angle): spin.setMaximumWidth(160); spin.setEnabled(not self.read_only)
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
            box = QGroupBox(display_name); box.setCheckable(True); box.setChecked(group.included); box.setCheckable(not self.read_only); box.setObjectName("drillingGroupCard")
            outer = QVBoxLayout(box); identity = QFormLayout(); outer.addLayout(identity)
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
                builder_layout.addWidget(builder); state["builder"]=builder; state["last_depth"]=depth
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
            box.toggled.connect(lambda checked,g=group:(setattr(g,"included",checked),refresh()))
            load.clicked.connect(lambda _=False,c=combo,g=group:self._load_preset(c,g,state,refresh))
            save.clicked.connect(lambda _=False,c=combo,g=group:self._save_preset(c,g))
            update.clicked.connect(lambda _=False,c=combo,g=group:self._update_preset(c,g))
            delete.clicked.connect(lambda _=False,c=combo:self._delete_preset(c))
            actions = QHBoxLayout(); duplicate = QPushButton(tr("Duplicate")); remove = QPushButton(tr("Delete"))
            duplicate.setEnabled(not self.read_only); remove.setEnabled(not self.read_only)
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
        layout = self._scroll_tab(tr("Execution fact")); execution = QGroupBox(tr("A. Completion status")); form = QFormLayout(execution)
        self.completion_status = QComboBox()
        for key, name in (("planned","Planned"),("drilling","Drilling"),("charged","Charged"),("blasted","Blasted"),("completed","Completed"),("rejected","Rejected")): self.completion_status.addItem(tr(name),key)
        actual=self.revision.actual_execution; self.completion_status.setCurrentIndex(self.completion_status.findData(actual.completion_status)); form.addRow(tr("Status"), self.completion_status)
        self.actual_date=QLineEdit(actual.actual_blast_date or ""); self.execution_notes=QTextEdit(actual.execution_notes); self.execution_notes.setMaximumHeight(70)
        form.addRow(tr("Actual blast date (YYYY-MM-DD)"),self.actual_date); form.addRow(tr("General notes"),self.execution_notes); layout.addWidget(execution)
        summary=QGroupBox(tr("B. Actual summary")); grid=QFormLayout(summary); self.actual_summary_widgets={}
        for label,attr in (("Actual area, m²","actual_drilling_area_m2"),("Accepted block volume, m³","actual_block_volume_m3"),
            ("Total holes","actual_total_hole_count"),("Total drilling length, m","actual_total_drilling_length_m"),
            ("Total explosive mass, kg","actual_total_explosive_mass_kg"),("Average depth, m","actual_average_depth_m"),
            ("Rock yield, m³/m","actual_rock_yield_m3_per_drilling_m"),("Specific drilling, m/m³","actual_specific_drilling_m_per_m3"),
            ("Powder factor, kg/m³","actual_powder_factor_kg_per_m3"),("Rejected holes","rejected_hole_count"),
            ("Redrilled holes","redrilled_hole_count"),("Wet holes","wet_hole_count"),("Uncharged holes","uncharged_hole_count")):
            self.actual_summary_widgets[attr]=self._add_number(grid,label,actual,attr)
        layout.addWidget(summary)
        controls=QHBoxLayout(); copy_all=QPushButton(tr("Copy design to actual")); copy_all.setObjectName("copyProjectToActualButton")
        add=QPushButton(tr("+ Add actual group")); copy_all.clicked.connect(self._copy_all_actual); add.clicked.connect(self._add_actual_group)
        controls.addWidget(copy_all); controls.addWidget(add); controls.addStretch(); layout.addLayout(controls)
        section=QGroupBox(tr("C. Actual drilling and charging groups")); self.actual_cards_layout=QVBoxLayout(section); layout.addWidget(section)
        comparison=QGroupBox(tr("D. Design / actual comparison")); comparison_layout=QVBoxLayout(comparison)
        self.comparison_table=QTableWidget(); self.comparison_table.setObjectName("projectActualComparisonTable"); comparison_layout.addWidget(self.comparison_table); layout.addWidget(comparison)
        self._render_actual_groups(); self._refresh_actual_summary()

    def _render_actual_groups(self):
        while self.actual_cards_layout.count():
            item=self.actual_cards_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        designs={g.id:g for g in self.revision.drilling_groups}
        for group in self.revision.actual_execution.actual_drilling_groups:
            design=designs.get(group.design_group_id); flags=[]
            if group.copied_from_design: flags.append("Copied from design")
            if group.design_group_id is None: flags.append("Not in design")
            display_name=technical_group_label(group.group_type, group.name)
            box=QGroupBox(display_name + (f"  [{'; '.join(tr(flag) for flag in flags)}]" if flags else "")); box.setCheckable(True); box.setChecked(True)
            design_name=technical_group_label(design.group_type, design.name) if design else "—"
            outer=QVBoxLayout(box); outer.addWidget(QLabel(f"{tr('Linked design group')}: {design_name}"))
            drilling=QGroupBox(tr("Drilling")); f=QFormLayout(drilling)
            for label,attr,integer in (("Holes, count","hole_count",True),("Diameter, mm","diameter_mm",False),("Average depth, m","average_depth_m",False),
                ("Subdrill, m","subdrill_m",False),(BURDEN_LABEL,"burden_m",False),(SPACING_LABEL,"spacing_m",False),("Rows","row_count",True),
                ("Inclination, °","inclination_deg",False),("Azimuth, °","azimuth_deg",False),("Drilling length, m","drilling_length_m",False),
                (TOE_LABEL,"toe_standoff_m",False),("Rejected holes","rejected_hole_count",True),("Redrilled holes","redrilled_hole_count",True),("Wet holes","wet_hole_count",True)):
                self._add_number(f,label,group,attr,integer=integer)
            outer.addWidget(drilling); charging=QGroupBox(tr("Charging")); cf=QFormLayout(charging)
            for label,attr,integer in (("Mass per hole, kg","charge_mass_per_hole_kg",False),("Concentration, kg/m","charge_concentration_kg_per_m",False),
                ("Total mass, kg","total_charge_mass_kg",False),("Stemming, m","stemming_length_m",False),("Delay, ms","delay_ms",False),
                ("Air decks","air_deck_count",True),("Uncharged holes","uncharged_hole_count",True)):
                self._add_number(cf,label,group,attr,integer=integer)
            for label,attr in (("Explosive type","explosive_type"),("Charge construction","charge_construction_text"),("Initiation","initiation_sequence"),("Deck notes","deck_notes")):
                edit=QLineEdit(getattr(group,attr)); edit.textChanged.connect(lambda v,g=group,a=attr:setattr(g,a,v)); cf.addRow(tr(label),edit)
            outer.addWidget(charging); deviation=QGroupBox(tr("Deviations")); df=QFormLayout(deviation)
            for label,attr in (("Deviation description","deviations_text"),("Notes","notes")):
                edit=QLineEdit(getattr(group,attr)); edit.textChanged.connect(lambda v,g=group,a=attr:setattr(g,a,v)); df.addRow(tr(label),edit)
            outer.addWidget(deviation); actions=QHBoxLayout(); copy=QPushButton(tr("Copy from design")); duplicate=QPushButton(tr("Duplicate")); remove=QPushButton(tr("Delete"))
            copy.setEnabled(design is not None); copy.clicked.connect(lambda _=False,d=design,a=group:self._copy_one_actual(d,a)); duplicate.clicked.connect(lambda _=False,g=group:self._duplicate_actual(g)); remove.clicked.connect(lambda _=False,g=group:self._remove_actual(g))
            for button in (copy,duplicate,remove): actions.addWidget(button)
            outer.addLayout(actions); self.actual_cards_layout.addWidget(box)
        self._render_comparison()

    def _copy_all_actual(self):
        actual=self.revision.actual_execution
        if not actual.actual_drilling_groups:
            if QMessageBox.question(self,tr("Copy design"),tr("Create an independent snapshot of design groups in actuals?")) != QMessageBox.StandardButton.Yes: return
            mode="replace"
        else:
            labels=["Fill empty fields only","Add missing groups","Replace actuals with design","Cancel"]
            choice,ok=QInputDialog.getItem(self,tr("Copy design"),tr("Choose a safe copy mode:"),labels,0,False)
            if not ok or choice=="Cancel": return
            mode={labels[0]:"fill_empty",labels[1]:"add_missing",labels[2]:"replace"}[choice]
            if mode=="replace" and QMessageBox.warning(self,tr("Replace actuals"),tr("All entered actual values will be replaced with design values."),QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Ok: return
        actual.copy_from_design(self.revision.drilling_groups,self.revision.id or None,mode); self._render_actual_groups(); self._refresh_actual_summary()

    def _copy_one_actual(self, design, actual):
        if design is None: return
        labels=["Fill empty fields only","Replace group","Cancel"]
        choice,ok=QInputDialog.getItem(self,tr("Copy from design"),tr("Actual values may already be populated:"),labels,0,False)
        if not ok or choice==labels[2]: return
        mode="fill_empty" if choice==labels[0] else "replace"
        self.revision.actual_execution.copy_one(design,actual,self.revision.id or None,mode)
        self.revision.actual_execution.recalculate(); self._render_actual_groups(); self._refresh_actual_summary()

    def _add_actual_group(self):
        catalogue=PRODUCTION_GROUP_TYPES if self.blast_event.event_type=="production" else CONTOUR_GROUP_TYPES
        keys=list(catalogue); names=[technical_group_label(key) for key in keys]; choice,ok=QInputDialog.getItem(self,tr("Actual group"),tr("Group type:"),names,0,False)
        if not ok:return
        kind=keys[names.index(choice)]
        self.revision.actual_execution.actual_drilling_groups.append(ActualDrillingGroup(design_group_id=None,group_type=kind,name=choice,sequence_order=len(self.revision.actual_execution.actual_drilling_groups)+1))
        self._render_actual_groups(); self._refresh_actual_summary()

    def _duplicate_actual(self, group):
        from copy import deepcopy
        from uuid import uuid4
        copied=deepcopy(group); copied.id=f"AG-{uuid4().hex}"; copied.design_group_id=None; copied.copied_from_design=False; copied.copied_from_technical_revision_id=None; copied.copied_at=None; copied.name += " (copy)"
        self.revision.actual_execution.actual_drilling_groups.append(copied); self._render_actual_groups()

    def _remove_actual(self, group):
        self.revision.actual_execution.actual_drilling_groups.remove(group); self._render_actual_groups(); self._refresh_actual_summary()

    def _refresh_actual_summary(self):
        actual=self.revision.actual_execution; actual.recalculate()
        for attr,widget in self.actual_summary_widgets.items():
            value=getattr(actual,attr); widget.blockSignals(True); widget.setValue(value if value is not None else widget.minimum()); widget.blockSignals(False)
        self._render_comparison()

    def _render_comparison(self):
        if not hasattr(self,"comparison_table"): return
        rows=self.revision.comparison_rows(); table=self.comparison_table; table.setRowCount(len(rows)); table.setColumnCount(6)
        table.setHorizontalHeaderLabels([tr("Group"),tr("Parameter"),tr("Design"),tr("Execution fact"),tr("Absolute deviation"),tr("Relative deviation, %")])
        def display(value,unit=""): return "—" if value is None else f"{value:g} {unit}".strip()
        for row,data in enumerate(rows):
            unit = technical_text(data["unit"])
            values=(technical_text(data["group"]),technical_text(data["parameter"]),display(data["project"],unit),display(data["actual"],unit),display(data["absolute_deviation"],unit),display(data["relative_deviation_percent"],"%"))
            for column,value in enumerate(values): table.setItem(row,column,QTableWidgetItem(value))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.resizeColumnsToContents()

    def _history_tab(self):
        layout = self._scroll_tab(tr("Revision history")); table = QTableWidget(len(self.card.revisions), 5); table.setHorizontalHeaderLabels(["№", tr("Date"), tr("Status"), tr("Geometry revision"), tr("Reason")])
        for row, revision in enumerate(self.card.revisions):
            for col, value in enumerate((revision.revision_number, revision.created_at.isoformat(sep=" ", timespec="minutes"), revision.status, revision.geometry_revision_id, revision.change_reason)): table.setItem(row,col,QTableWidgetItem(str(value)))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.horizontalHeader().setStretchLastSection(True); layout.addWidget(table)

    def _save(self, status):
        if self.read_only:
            QMessageBox.warning(self, tr("Read only"), tr("Archived entities and Viewer accounts cannot change the Technical Card."))
            return False
        self.revision.common_parameters.block_name = self.block_name.text(); self.revision.common_parameters.comments = self.comments.text()
        try:
            azimuth=self._optional_number(self.design_slope_azimuth)
            if azimuth==360: azimuth=0.0; self.design_slope_azimuth.setValue(0.0)
            self.revision.design_slope_orientation=DesignSlopeOrientation(azimuth,self._optional_number(self.design_slope_angle))
            if self.revision.production_parameters:
                p=self.revision.production_parameters; p.design_bench_height_m=None if self.bench_height.value()==self.bench_height.minimum() else self.bench_height.value()
                self.revision.geomechanical_parameters = self._geomechanics_from_form()
        except ValueError as exc:
            QMessageBox.warning(self, tr("Technical Card validation"), domain_message(str(exc))); return False
        actual=self.revision.actual_execution; actual.completion_status=self.completion_status.currentData(); actual.actual_blast_date=self.actual_date.text().strip() or None; actual.execution_notes=self.execution_notes.toPlainText(); actual.recalculate()
        planned_date = self.planned_date.date().toPython() if self.has_planned_date.isChecked() else None
        try: self.save_callback(self.card, self.revision, status, planned_date)
        except ValueError as exc: QMessageBox.warning(self, tr("Technical Card validation"), domain_message(str(exc))); return False
        except Exception as exc:
            QMessageBox.critical(self, tr("Technical Card"), f"Could not save changes. The data remains in the form.\n\n{exc}")
            return False
        self.accept(); return True
