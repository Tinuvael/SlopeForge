"""Usable, revision-safe Qt editor for Assessment Area wall assessments."""
from __future__ import annotations

from app.localization import tr

from copy import deepcopy
from PySide6.QtCore import QDate, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from prototype_2d.wall_assessment import (
    CONDITION, DESIGN, AssessmentCriterionResult, AssessmentMatrixTemplate,
    calculate_revision,
)
from ui.presentation_labels import (
    CRITERION_HELP, criterion_label, domain_message, matrix_label, option_label, result_label,
)

DAMAGE_WARNING = "The matrix has no automatic score for the range of 1–5 features/m²."


class NullableDoubleSpinBox(QDoubleSpinBox):
    """A spin box whose initial/sentinel state is None; explicit zero stays zero."""
    nullableValueChanged = Signal(object)

    def __init__(self, maximum=999.0, parent=None):
        super().__init__(parent)
        self._sentinel = -0.01
        self.setRange(self._sentinel, maximum)
        self.setDecimals(2)
        self.setSpecialValueText("—")
        self.setValue(self._sentinel)
        self.valueChanged.connect(lambda _value: self.nullableValueChanged.emit(self.nullable_value()))
        self.setToolTip(tr("Required for completion. Clear resets the value to —."))

    def nullable_value(self):
        return None if self.value() == self.minimum() else float(self.value())

    def set_nullable_value(self, value):
        self.setValue(self.minimum() if value is None else float(value))

    def clear_value(self):
        self.set_nullable_value(None)


class QuadrantPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.template = self.design = self.condition = None
        self.setMinimumSize(420, 300)

    def set_result(self, template, design, condition):
        self.template, self.design, self.condition = template, design, condition
        self.setToolTip("" if design is None or condition is None else
                        f"DAI: {design:.3f}\nFCI: {condition:.3f}")
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(55, 20, max(10, self.width() - 75), max(10, self.height() - 65))
        if not self.template:
            return
        x = self.template.face_condition_threshold
        y = self.template.design_achievement_threshold
        px, py = rect.left() + x * rect.width(), rect.bottom() - y * rect.height()
        regions = (
            (QRectF(rect.left(), rect.top(), px-rect.left(), py-rect.top()), "#f6df72", tr("Geometry achieved, condition insufficient")),
            (QRectF(px, rect.top(), rect.right()-px, py-rect.top()), "#8bd17c", tr("Good results")),
            (QRectF(rect.left(), py, px-rect.left(), rect.bottom()-py), "#ef7770", tr("Unacceptable results")),
            (QRectF(px, py, rect.right()-px, rect.bottom()-py), "#f2b764", tr("Condition good, geometry unacceptable")),
        )
        for region, colour, label in regions:
            painter.fillRect(region, QColor(colour))
            painter.drawText(region.adjusted(5, 5, -5, -5), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, label)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRect(rect); painter.drawLine(px, rect.top(), px, rect.bottom()); painter.drawLine(rect.left(), py, rect.right(), py)
        painter.drawText(rect.left(), self.height()-10, tr("Face condition (FCI) →"))
        painter.save(); painter.translate(15, rect.bottom()); painter.rotate(-90); painter.drawText(0, 0, tr("Design achievement (DAI) →")); painter.restore()
        if self.design is not None and self.condition is not None:
            cx, cy = rect.left()+self.condition*rect.width(), rect.bottom()-self.design*rect.height()
            painter.setBrush(QColor("#1261a0")); painter.setPen(QPen(Qt.GlobalColor.white, 2)); painter.drawEllipse(QRectF(cx-7, cy-7, 14, 14))


class CriterionEditor(QWidget):
    changed = Signal()

    def __init__(self, criterion, parent=None):
        super().__init__(parent)
        self.criterion = criterion
        root = QVBoxLayout(self); root.setContentsMargins(0, 2, 0, 8)
        top = QHBoxLayout(); self.title = QLabel(f"<b>{criterion_label(criterion.id, criterion.name)}</b>"); self.title.setWordWrap(True); top.addWidget(self.title, 1)
        self.clear_button = None
        if criterion.kind in ("numeric", "damage"):
            self.input = NullableDoubleSpinBox(100 if criterion.id == "visible_drillhole_traces" else 999)
            self.input.nullableValueChanged.connect(self.changed)
            self.clear_button = QPushButton(tr("Clear")); self.clear_button.clicked.connect(self.input.clear_value)
            top.addWidget(self.input); top.addWidget(self.clear_button)
        else:
            self.input = QComboBox(); self.input.addItem(tr("— select observation —"), None)
            for option in criterion.options:
                self.input.addItem(f"{option_label(option.id, option.label)} — {option.score:g} points", option.id)
            self.input.currentIndexChanged.connect(self.changed); top.addWidget(self.input, 1)
        root.addLayout(top)
        if criterion.help_text:
            help_label = QLabel(CRITERION_HELP.get(criterion.id, criterion.help_text)); help_label.setWordWrap(True); help_label.setStyleSheet("color:#555"); root.addWidget(help_label)
        self.validation = QLabel(); self.validation.setWordWrap(True); self.validation.setStyleSheet("color:#a33"); root.addWidget(self.validation)
        self.override_toggle = QCheckBox(tr("Override score manually"))
        self.override_toggle.toggled.connect(self._toggle_override); self.override_toggle.toggled.connect(self.changed); root.addWidget(self.override_toggle)
        self.override_panel = QWidget(); override = QFormLayout(self.override_panel); override.setContentsMargins(18, 0, 0, 0)
        self.auto_score = QLabel(tr("—"))
        self.manual_score = NullableDoubleSpinBox(criterion.maximum_score)
        self.manual_score.nullableValueChanged.connect(self.changed)
        self.reason = QLineEdit(); self.reason.textChanged.connect(self.changed)
        self.notes = QTextEdit(); self.notes.setMaximumHeight(55); self.notes.textChanged.connect(self.changed)
        self.accepted = QLabel(tr("—"))
        override.addRow(tr("Automatic score"), self.auto_score)
        override.addRow(f"Manual score (0–{criterion.maximum_score:g})", self.manual_score)
        override.addRow(tr("Reason (required)"), self.reason)
        override.addRow(tr("Notes"), self.notes)
        override.addRow(tr("Accepted score"), self.accepted)
        root.addWidget(self.override_panel); self.override_panel.hide()

    def _toggle_override(self, checked):
        self.override_panel.setVisible(checked)

    def restore(self, result):
        if result:
            if isinstance(self.input, NullableDoubleSpinBox): self.input.set_nullable_value(result.raw_numeric_value)
            else:
                index = self.input.findData(result.selected_option_id); self.input.setCurrentIndex(max(index, 0))
            self.manual_score.set_nullable_value(result.manual_score)
            self.reason.setText(result.override_reason or ""); self.notes.setPlainText(result.notes or "")
            self.override_toggle.setChecked(result.manual_score is not None or bool(result.override_reason or result.notes))

    def result(self):
        numeric = self.input.nullable_value() if isinstance(self.input, NullableDoubleSpinBox) else None
        selected = self.input.currentData() if isinstance(self.input, QComboBox) else None
        manual = self.manual_score.nullable_value() if self.override_toggle.isChecked() else None
        return AssessmentCriterionResult(
            self.criterion.id, self.criterion.name, self.criterion.section,
            raw_numeric_value=numeric, selected_option_id=selected,
            manual_score=manual, maximum_score=self.criterion.maximum_score,
            override_reason=self.reason.text().strip() if self.override_toggle.isChecked() else None,
            notes=self.notes.toPlainText().strip(),
        )


class AssessmentAreaEvaluationDialog(QDialog):
    """Edits a private copy. Construction and live previews never mutate source objects."""
    def __init__(self, area, evaluation, draft, save_callback, parent=None, read_only=False,
                 attachment_service=None, unsaved=False):
        super().__init__(parent)
        self.area, self.evaluation, self.source_revision = area, evaluation, draft
        self.draft = deepcopy(draft)
        self.save_callback, self.read_only = save_callback, read_only
        self.attachment_service, self.unsaved = attachment_service, unsaved
        self.template = AssessmentMatrixTemplate.from_dict(self.draft.matrix_template_snapshot)
        self._initializing = True; self._dirty = False; self._allow_close = False; self._preview = deepcopy(self.draft)
        self.setWindowTitle(self._base_title()); self.resize(1120, 780)
        root = QVBoxLayout(self); self.tabs = QTabWidget(); root.addWidget(self.tabs)
        self._general(); self._geometry(); self._condition(); self._matrix(); self._events(); self._attachments(); self._history()
        buttons = QHBoxLayout(); buttons.addStretch()
        self.draft_button = QPushButton(tr("Save draft")); self.complete_button = QPushButton(tr("Complete assessment")); self.cancel_button = QPushButton(tr("Close") if read_only else "Cancel")
        self.draft_button.clicked.connect(lambda: self.save("draft")); self.complete_button.clicked.connect(lambda: self.save("completed")); self.cancel_button.clicked.connect(self.reject)
        for button in (self.draft_button, self.complete_button, self.cancel_button): buttons.addWidget(button)
        self.draft_button.setVisible(not read_only); self.complete_button.setVisible(not read_only); root.addLayout(buttons)
        self._restore_controls()
        self._connect_general_signals()
        self._initializing = False
        if self.draft.status == "completed":
            self._preview = deepcopy(self.draft)
            self._render_preview(self._preview)
        else:
            self.refresh(mark_dirty=False)
        self._dirty = False; self._update_title()
        if read_only: self._set_read_only()

    def _base_title(self):
        suffix = f" — revision {self.draft.revision_number} ({self.draft.status})" if self.draft.revision_number else ""
        return "Face assessment" + suffix

    def take_tab(self, title: str, parent: QWidget | None = None) -> QWidget:
        """Detach a page from the dialog and give it explicit, durable ownership."""
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                page = self.tabs.widget(index)
                self.tabs.removeTab(index)
                page.setParent(parent)
                return page
        raise LookupError(f"Assessment editor tab not found: {title}")

    def _connect_general_signals(self):
        self.date.dateChanged.connect(self._changed); self.inspector.textChanged.connect(self._changed)
        self.comments.textChanged.connect(self._changed); self.recommendations.textChanged.connect(self._changed)
        self.override_reason.textChanged.connect(self._changed); self.method.textChanged.connect(self._changed); self.measure_notes.textChanged.connect(self._changed)

    def _general(self):
        page = QWidget(); form = QFormLayout(page)
        self.date = QDateEdit(); self.date.setCalendarPopup(True)
        self.inspector = QLineEdit(); self.override_reason = QLineEdit()
        self.detected = QLabel(tr("Contour drilling detected from a confirmed link") if self.draft.controlled_blasting_present else "No confirmed contour event found")
        self.comments = QTextEdit(); self.recommendations = QTextEdit()
        revision = next(r for r in self.area.geometry_revisions if r.id == self.draft.assessment_area_geometry_revision_id)
        form.addRow(tr("Assessment date"), self.date); form.addRow(tr("Inspector"), self.inspector)
        form.addRow(tr("Assessment Area ID"), QLabel(self.area.id)); form.addRow(tr("Geometry revision"), QLabel(revision.id))
        form.addRow(tr("Elevations"), QLabel(f"{revision.lower_elevation:g} — {revision.upper_elevation:g}"))
        form.addRow(tr("Matrix"), QLabel(matrix_label(self.template.id, self.template.name))); form.addRow(tr("Detection"), self.detected)
        form.addRow(tr("Manual matrix selection reason"), self.override_reason); form.addRow(tr("Comments"), self.comments); form.addRow(tr("Recommendations"), self.recommendations)
        self.tabs.addTab(page, tr("General"))

    def _nullable(self, maximum=999):
        control = NullableDoubleSpinBox(maximum); control.nullableValueChanged.connect(self._changed); return control

    def _geometry(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); page = QWidget(); form = QFormLayout(page)
        self.da = self._nullable(90); self.aa = self._nullable(90); self.db = self._nullable(); self.ab = self._nullable(); self.toe = self._nullable()
        self.shortfall = QLabel(tr("—")); self.deficit = QLabel(tr("—"))
        self.angle_score = QLabel(tr("Required")); self.berm_score = QLabel(tr("Required")); self.toe_score = QLabel(tr("Required"))
        self.method = QLineEdit(); self.measure_notes = QTextEdit()
        self.geometry_editors = {}
        for criterion in self.template.section(DESIGN).criteria:
            editor = CriterionEditor(criterion)
            editor.title.setText(f"Expert override: {criterion_label(criterion.id, criterion.name)}")
            editor.input.hide()
            if editor.clear_button: editor.clear_button.hide()
            editor.changed.connect(self._changed)
            self.geometry_editors[criterion.id] = editor
        form.addRow(tr("Design bench face angle, °"), self.da); form.addRow(tr("Actual bench face angle, °"), self.aa)
        form.addRow(tr("Angle shortfall from design, °"), self.shortfall); form.addRow(tr("Angle score"), self.angle_score); form.addRow("", self.geometry_editors["bench_angle"])
        form.addRow(tr("Design berm width, m"), self.db); form.addRow(tr("Actual berm width, m"), self.ab)
        form.addRow(tr("Width deficit from design, m"), self.deficit); form.addRow(tr("Berm score"), self.berm_score); form.addRow("", self.geometry_editors["berm_width"])
        form.addRow(tr("Actual toe deviation from design, m"), self.toe); form.addRow(tr("Toe score"), self.toe_score); form.addRow("", self.geometry_editors["toe_position"])
        toe_help = QLabel(tr("Enter the absolute distance between actual and design toe positions.")); toe_help.setWordWrap(True); form.addRow("", toe_help)
        rules = QLabel(self._geometry_rules()); rules.setWordWrap(True); rules.setStyleSheet("background:#f3f5f7;padding:10px"); form.addRow(tr("Scoring rules"), rules)
        form.addRow(tr("Measurement method"), self.method); form.addRow(tr("Measurement notes"), self.measure_notes)
        scroll.setWidget(page); self.tabs.addTab(scroll, tr("Geometry"))

    def _geometry_rules(self):
        if self.template.id == "controlled_blasting_v1":
            angle = "meets design or is steeper — 50; shortfall ≤3° — 25; >3–5° — 10; >5° — 0"
            toe = "meets design — 10; <1 m — 8; 1–<2 m — 5; ≥2 m — 0"
        else:
            angle = "meets design — 40; then minus 4 points per started degree; ≥10° — 0 (2,4° is scored as 3°)"
            toe = "meets design — 20; <1 m — 15; 1–<2 m — 5; ≥2 m — 0"
        return (f"Angle: {angle}.\nBerm: meets or exceeds design — 40; deficit <1 m — 35; "
                f"1–<2 m — 25; 2–<3 m — 15; ≥3 m — 0.\nToe: {toe}.")

    def _condition(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); page = QWidget(); layout = QVBoxLayout(page); self.editors = {}
        visible_rules = ">=80%: 20; 70–<80%: 15; 60–<70%: 12; 50–<60%: 8; 30–<50%: 5; 10–<30%: 2; <10%: 0."
        crest_rules = "0 m: 15; >0–<1 m: 12; 1–<2 m: 10; 2–<3 m: 5; ≥3 m: 0."
        for criterion in self.template.section(CONDITION).criteria:
            editor = CriterionEditor(criterion); editor.changed.connect(self._changed); self.editors[criterion.id] = editor; layout.addWidget(editor)
            if criterion.id == "visible_drillhole_traces": editor.validation.setToolTip(visible_rules); editor.title.setToolTip(visible_rules)
            if criterion.id == "crest_loss": editor.validation.setToolTip(crest_rules); editor.title.setToolTip(crest_rules)
        layout.addStretch(); scroll.setWidget(page); self.tabs.addTab(scroll, tr("Face condition"))

    def _matrix(self):
        page = QWidget(); layout = QVBoxLayout(page); tables = QHBoxLayout(); self.design_table = QTableWidget(); self.condition_table = QTableWidget()
        headers = [tr("Criterion"), tr("Entered / selected"), tr("Threshold / category"), tr("Auto"), tr("Manual"), tr("Accepted"), tr("Max."), tr("Note")]
        for table, title in ((self.design_table, "Design results"), (self.condition_table, "Face condition results")):
            box = QVBoxLayout(); box.addWidget(QLabel(f"<b>{tr(title)}</b>")); table.setColumnCount(len(headers)); table.setHorizontalHeaderLabels(headers); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); box.addWidget(table); tables.addLayout(box)
        layout.addLayout(tables); self.summary = QLabel(); self.summary.setWordWrap(True); layout.addWidget(self.summary); self.plot = QuadrantPlot(); layout.addWidget(self.plot); self.tabs.addTab(page, tr("Matrix"))

    def _events(self):
        table = QTableWidget(len(self.draft.linked_event_snapshots), 4); table.setHorizontalHeaderLabels([tr("BlastEvent"), tr("Type"), tr("Elevation"), tr("Card revision")]); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, event in enumerate(self.draft.linked_event_snapshots):
            for column, value in enumerate((event.blast_event_name, event.event_type, f"{event.event_elevation:g}", event.technical_card_revision_id or "—")): table.setItem(row, column, QTableWidgetItem(value))
        self.tabs.addTab(table, tr("Linked events"))

    def _history(self):
        self.history = QTableWidget(0, 8); self.history.setHorizontalHeaderLabels(["№", tr("Date"), tr("Status"), tr("Geometry"), tr("Matrix"), tr("Design"), tr("Condition"), tr("Result")]); self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.refresh_history()
        self.history.cellDoubleClicked.connect(self._open_history)
        container = QWidget(); layout = QVBoxLayout(container); hint = QLabel(tr("Double-click a row to open a read-only historical revision.")); layout.addWidget(hint); layout.addWidget(self.history); self.tabs.addTab(container, tr("History"))

    def refresh_history(self):
        self.history.setRowCount(len(self.evaluation.revisions))
        for row, revision in enumerate(self.evaluation.revisions):
            values = (revision.revision_number, revision.assessment_date or "—", revision.status, revision.assessment_area_geometry_revision_id, revision.matrix_template_id, "—" if revision.design_achievement_index is None else f"{revision.design_achievement_index:.3f}", "—" if revision.face_condition_index is None else f"{revision.face_condition_index:.3f}", result_label(revision.result_label) or "—")
            for column, value in enumerate(values): self.history.setItem(row, column, QTableWidgetItem(str(value)))

    def _attachments(self):
        page = QWidget(); layout = QVBoxLayout(page)
        info = QLabel(tr("Files belong to the assessment and are shared by all revisions.")); info.setWordWrap(True); layout.addWidget(info)
        if self.attachment_service is None:
            layout.addWidget(QLabel(tr("File storage is unavailable.")))
        else:
            photos, documents = self.attachment_service.counts("assessment_evaluation", self.evaluation.id)
            self.attachment_counts = QLabel(f"{tr('Photos')}: {photos}    {tr('Documents')}: {documents}"); layout.addWidget(self.attachment_counts)
            manage = QPushButton(tr("Photos and documents")); manage.clicked.connect(self._open_attachments); layout.addWidget(manage)
        layout.addStretch(); self.tabs.addTab(page, tr("Photos and documents"))

    def _open_attachments(self):
        from ui.dialogs.entity_attachment_dialog import EntityAttachmentDialog
        EntityAttachmentDialog(self.attachment_service, "assessment_evaluation", self.evaluation.id, self,
            read_only=self.read_only or self.area.is_archived, unsaved=self.unsaved).exec()
        photos, documents = self.attachment_service.counts("assessment_evaluation", self.evaluation.id)
        self.attachment_counts.setText(f"{tr('Photos')}: {photos}    {tr('Documents')}: {documents}")

    def _open_history(self, row, _column):
        if 0 <= row < len(self.evaluation.revisions):
            AssessmentAreaEvaluationDialog(self.area, self.evaluation, self.evaluation.revisions[row], None, self,
                read_only=True, attachment_service=self.attachment_service).exec()

    def _restore_controls(self):
        d = self.draft.design_inputs or {}; results = {r.criterion_id: r for r in self.draft.criterion_results}
        if self.draft.assessment_date: self.date.setDate(QDate(self.draft.assessment_date.year, self.draft.assessment_date.month, self.draft.assessment_date.day))
        self.inspector.setText(self.draft.inspector); self.comments.setPlainText(self.draft.comments); self.recommendations.setPlainText(self.draft.recommendations); self.override_reason.setText(self.draft.change_reason or "")
        self.da.set_nullable_value(d.get("design_bench_face_angle_deg")); self.aa.set_nullable_value(d.get("actual_bench_face_angle_deg")); self.db.set_nullable_value(d.get("design_berm_width_m")); self.ab.set_nullable_value(d.get("actual_berm_width_m")); self.toe.set_nullable_value(d.get("toe_offset_from_design_m")); self.method.setText(d.get("measurement_method", "")); self.measure_notes.setPlainText(d.get("measurement_notes", ""))
        for criterion_id, editor in self.geometry_editors.items(): editor.restore(results.get(criterion_id))
        face = self.draft.face_condition_inputs or {}
        for criterion_id, editor in self.editors.items():
            result = results.get(criterion_id)
            if result is None and criterion_id in face:
                result = AssessmentCriterionResult(criterion_id, editor.criterion.name, CONDITION, raw_numeric_value=face.get(criterion_id))
            editor.restore(result)

    def _changed(self, *_args):
        if self._initializing or self.read_only: return
        self.refresh(mark_dirty=True)

    def collect(self):
        """Return a new preview object; never mutate self.draft or a saved revision."""
        revision = deepcopy(self.draft)
        revision.assessment_date = self.date.date().toPython(); revision.inspector = self.inspector.text().strip(); revision.comments = self.comments.toPlainText(); revision.recommendations = self.recommendations.toPlainText(); revision.change_reason = self.override_reason.text().strip()
        da, aa, db, ab, toe = self.da.nullable_value(), self.aa.nullable_value(), self.db.nullable_value(), self.ab.nullable_value(), self.toe.nullable_value()
        shortfall = max(da-aa, 0) if da is not None and aa is not None else None; deficit = max(db-ab, 0) if db is not None and ab is not None else None
        revision.design_inputs = {"design_bench_face_angle_deg": da, "actual_bench_face_angle_deg": aa, "bench_angle_shortfall_deg": shortfall, "design_berm_width_m": db, "actual_berm_width_m": ab, "berm_width_deficit_m": deficit, "toe_offset_from_design_m": abs(toe) if toe is not None else None, "measurement_method": self.method.text().strip(), "measurement_notes": self.measure_notes.toPlainText()}
        values = {"bench_angle": shortfall, "berm_width": deficit, "toe_position": abs(toe) if toe is not None else None}
        results = []
        for criterion in self.template.section(DESIGN).criteria:
            override = self.geometry_editors[criterion.id].result()
            results.append(AssessmentCriterionResult(
                criterion.id, criterion.name, DESIGN, raw_numeric_value=values[criterion.id],
                manual_score=override.manual_score, maximum_score=criterion.maximum_score,
                override_reason=override.override_reason, notes=override.notes,
            ))
        face_inputs = {}
        for criterion in self.template.section(CONDITION).criteria:
            result = self.editors[criterion.id].result(); results.append(result)
            face_inputs[criterion.id] = result.raw_numeric_value if result.raw_numeric_value is not None else result.selected_option_id
        revision.face_condition_inputs = face_inputs; revision.criterion_results = results
        calculate_revision(revision)
        return revision

    def refresh(self, mark_dirty=True):
        if self._initializing: return
        preview = self.collect(); self._preview = preview
        if mark_dirty: self._dirty = True; self._update_title()
        self._render_preview(preview)

    def _render_preview(self, preview):
        """Render already-stored or live-calculated values without recalculating them."""
        d = preview.design_inputs
        self.shortfall.setText(tr("—") if d["bench_angle_shortfall_deg"] is None else f'{d["bench_angle_shortfall_deg"]:g}')
        self.deficit.setText(tr("—") if d["berm_width_deficit_m"] is None else f'{d["berm_width_deficit_m"]:g}')
        by_id = {r.criterion_id: r for r in preview.criterion_results}
        for label, cid in ((self.angle_score, "bench_angle"), (self.berm_score, "berm_width"), (self.toe_score, "toe_position")):
            result = by_id[cid]; label.setText(tr("Required") if result.accepted_score is None else f"{result.accepted_score:g} of {result.maximum_score:g}")
            editor = self.geometry_editors[cid]
            editor.auto_score.setText(tr("—") if result.automatic_score is None else f"{result.automatic_score:g}")
            editor.accepted.setText(tr("—") if result.accepted_score is None else f"{result.accepted_score:g}")
        for cid, editor in self.editors.items():
            result = by_id[cid]; editor.auto_score.setText(tr("—") if result.automatic_score is None else f"{result.automatic_score:g}"); editor.accepted.setText(tr("—") if result.accepted_score is None else f"{result.accepted_score:g}")
            value = result.raw_numeric_value
            if cid == "damage" and value is not None and 1 <= value <= 5:
                editor.validation.setText(DAMAGE_WARNING + " An expert score and reason are required.")
                if not editor.override_toggle.isChecked():
                    initializing = self._initializing; self._initializing = True
                    editor.override_toggle.setChecked(True)
                    self._initializing = initializing
            elif result.accepted_score is None: editor.validation.setText(tr("Required"))
            elif cid == "damage" and value is not None: editor.validation.setText(tr("Maximum applied: fewer than 1 feature/m².") if value < 1 else "0 points applied: more than 5 features/m².")
            else: editor.validation.setText("")
        self._fill_table(self.design_table, [by_id[c.id] for c in self.template.section(DESIGN).criteria])
        self._fill_table(self.condition_table, [by_id[c.id] for c in self.template.section(CONDITION).criteria])
        design = "—" if preview.design_achievement_index is None else f"{preview.design_achievement_index:.3f}"
        condition = "—" if preview.face_condition_index is None else f"{preview.face_condition_index:.3f}"
        result = result_label(preview.result_label) or tr("Result available after all criteria are completed")
        self.summary.setText(f"{tr('Design')}: {preview.design_achievement_points if preview.design_achievement_points is not None else '—'} / 100; DAI: {design}\n{tr('Condition')}: {preview.face_condition_points if preview.face_condition_points is not None else '—'} / 100; FCI: {condition}\n{tr('Result')}: {result}")
        self.plot.set_result(self.template, preview.design_achievement_index, preview.face_condition_index)

    def _fill_table(self, table, results):
        table.setRowCount(len(results))
        for row, result in enumerate(results):
            definition = self.template.criterion(result.criterion_id); option = next((o for o in definition.options if o.id == result.selected_option_id), None)
            observed = option_label(option.id, option.label) if option else ("—" if result.raw_numeric_value is None else f"{result.raw_numeric_value:g}")
            category = option_label(option.id, option.label) if option else self._applied_rule(result)
            warning = result.notes or ("An expert score and reason are required" if result.criterion_id == "damage" and result.raw_numeric_value is not None and 1 <= result.raw_numeric_value <= 5 and result.accepted_score is None else "Required" if result.accepted_score is None else "")
            values = (criterion_label(result.criterion_id, result.criterion_name_snapshot), observed, category, result.automatic_score, result.manual_score, result.accepted_score, result.maximum_score, warning)
            for column, value in enumerate(values):
                item = QTableWidgetItem("—" if value is None else str(value)); table.setItem(row, column, item)
                if result.accepted_score is None: item.setBackground(QColor("#ffe2e2"))

    def _applied_rule(self, result):
        if result.raw_numeric_value is None: return tr("Required")
        if result.criterion_id == "damage" and 1 <= result.raw_numeric_value <= 5: return tr("Intermediate range 1–5 features/m²")
        return tr("Automatic matrix threshold")

    def save(self, status):
        if self.read_only:
            QMessageBox.warning(self, tr("Read only"), tr("Archived Assessment Areas and Viewer accounts cannot change the evaluation."))
            return False
        try:
            revision = self.collect()
            calculate_revision(revision, require_complete=status == "completed")
            self.save_callback(self.evaluation, revision, status)
        except Exception as exc:  # persistence errors must keep the dialog open
            QMessageBox.critical(self, tr("Assessment not saved"), f"Could not save the assessment. Changes remain in the form.\n\n{domain_message(str(exc))}")
            return False
        self._dirty = False; self._allow_close = True; self._update_title()
        QMessageBox.information(self, tr("Assessment saved"), "Draft saved." if status == "draft" else "Assessment completed and saved.")
        super().accept(); return True

    def _update_title(self): self.setWindowTitle(self._base_title() + (" *" if self._dirty else ""))

    def _confirm_close(self):
        if not self._dirty or self.read_only: return "discard"
        box = QMessageBox(QMessageBox.Icon.Warning, "Unsaved changes", "The assessment has unsaved changes.", parent=self)
        save = box.addButton("Save draft", QMessageBox.ButtonRole.AcceptRole); discard = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole); keep = box.addButton("Continue editing", QMessageBox.ButtonRole.RejectRole)
        box.exec(); clicked = box.clickedButton()
        if clicked is save: return "saved" if self.save("draft") else "keep"
        if clicked is discard: return "discard"
        return "keep"

    def reject(self):
        action = self._confirm_close()
        if action == "discard": self._allow_close = True; super().reject()

    def closeEvent(self, event):
        if self._allow_close or self.read_only: event.accept(); return
        action = self._confirm_close()
        if action == "discard": self._allow_close = True; event.accept()
        else: event.ignore()

    def _set_read_only(self):
        for widget in self.findChildren(QWidget):
            if widget is self.cancel_button: continue
            if isinstance(widget, (QLineEdit, QTextEdit, QDateEdit, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton)):
                widget.setEnabled(False)
