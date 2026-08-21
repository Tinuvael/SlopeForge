"""Guided Assessment Area creation and focused boundary revision page."""
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout,
                              QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
                              QSizePolicy, QVBoxLayout, QWidget)

from app.localization import tr
from domain.assessment.geometry import ProjectLineSpan, StraightConnector, derive_elevation_summary
from ui.editors.assessment_geometry_editor import AssessmentGeometryEditorWidget
from ui.pages.entity_page_controller import EntityPageController
from ui.presentation_labels import domain_message, format_assessment_elevation_interval
from ui.widgets.assessment_wizard_stepper import AssessmentWizardStepper
from ui.widgets.design_system import set_button_role
from ui.theme import Spacing


class AssessmentAreaCreationPage(QWidget):
    """Persistent three-column workspace; only Review -> Save writes state."""

    area_created = Signal(str)
    cancelled = Signal()
    GENERAL, BOUNDARY, REVIEW, SAVE = range(4)

    def __init__(self, context, domain_id, domain_name, site_id, parent=None, edit_area_id=None):
        super().__init__(parent)
        self.controller = EntityPageController(context, domain_id)
        self.domain_name = domain_name
        self.edit_area_id = edit_area_id
        self.current_step = self.BOUNDARY if edit_area_id else self.GENERAL
        self._saving = False
        self._link_preview = None
        self._link_preview_error = False
        self.link_events_scroll = None
        self.link_event_rows = []
        self.editor = AssessmentGeometryEditorWidget(
            self.controller.state, self.controller.save_assessment_area_geometry, self,
            read_only=not context.current_user.can_edit,
        )
        area_context = self.controller.project_assessment_boundaries()
        self.editor.set_existing_area_context(
            item for item in area_context
            if not (item.domain_id == self.controller.domain_id
                    and item.assessment_area_id == edit_area_id)
        )
        if edit_area_id:
            area = self.controller.area(edit_area_id)
            if area is None:
                raise ValueError("Assessment Area is unavailable")
            self.editor.inspect_area(edit_area_id)

        self.setObjectName("assessmentWorkflowPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.CARD_HORIZONTAL, Spacing.CARD_VERTICAL,
                                Spacing.CARD_HORIZONTAL, Spacing.CARD_VERTICAL)
        root.setSpacing(Spacing.SM)
        title = QLabel(tr("Edit Assessment Area boundary") if edit_area_id else tr("Create Assessment Area"))
        title.setObjectName("EntityTitle"); root.addWidget(title)
        context = QLabel(tr("Domain: %1").replace("%1", domain_name or "—"))
        context.setObjectName("MutedText"); root.addWidget(context)
        self.stepper = AssessmentWizardStepper(); root.addWidget(self.stepper)

        workspace = QHBoxLayout(); workspace.setSpacing(10)
        self.info_card = self._card("assessmentInfoCard")
        self.info_card.setMinimumWidth(230); self.info_card.setMaximumWidth(300)
        self._build_info_card(self.info_card.layout())
        workspace.addWidget(self.info_card, 0)

        self.plan_card = self._card("assessmentPlanCard")
        self.plan_card.setMinimumWidth(390)
        plan_layout = self.plan_card.layout()
        header = QHBoxLayout(); header.setSpacing(Spacing.SM)
        self.plan_title = QLabel(); self.plan_title.setObjectName("assessmentCardTitle")
        header.addWidget(self.plan_title); header.addStretch(1)
        toolbar = QHBoxLayout(); toolbar.setSpacing(6)
        self.lines = QCheckBox(tr("Project Lines")); self.lines.setChecked(True)
        self.lines.toggled.connect(self.editor.set_project_lines_visible)
        self.fit = QPushButton(tr("Fit")); self.fit.clicked.connect(self.editor.fit_to_extent)
        self.start = QPushButton(tr("Edit boundary") if edit_area_id else tr("Draw boundary"))
        self.start.clicked.connect(self._start_drawing)
        self.back_vertex = QPushButton(tr("Undo")); self.back_vertex.clicked.connect(self.editor.undo_vertex)
        self.finish = QPushButton(tr("Finish boundary")); self.finish.clicked.connect(self.editor.finish_polygon)
        self.cancel_drawing = QPushButton(tr("Cancel drawing")); self.cancel_drawing.clicked.connect(self.editor.cancel_workflow)
        set_button_role(self.fit, "link"); set_button_role(self.start, "secondary")
        set_button_role(self.back_vertex, "link"); set_button_role(self.finish, "primary")
        set_button_role(self.cancel_drawing, "link")
        for control in (self.lines, self.fit, self.start, self.back_vertex, self.finish, self.cancel_drawing):
            toolbar.addWidget(control)
        header.addLayout(toolbar); plan_layout.addLayout(header)
        self.step_status = QLabel(); self.step_status.setObjectName("assessmentPlanStatus")
        plan_layout.addWidget(self.step_status); plan_layout.addWidget(self.editor, 1)
        workspace.addWidget(self.plan_card, 1)

        self.context_card = self._card("assessmentContextCard")
        self.context_card.setMinimumWidth(220); self.context_card.setMaximumWidth(290)
        self.context_title = QLabel(); self.context_title.setObjectName("assessmentCardTitle")
        self.context_body = QVBoxLayout(); self.context_body.setSpacing(7)
        self.context_card.layout().addWidget(self.context_title)
        self.context_card.layout().addLayout(self.context_body)
        self.context_card.layout().addStretch(1)
        workspace.addWidget(self.context_card, 0)
        root.addLayout(workspace, 1)

        self.footer = QFrame(); self.footer.setObjectName("assessmentFooter")
        footer_layout = QHBoxLayout(self.footer); footer_layout.setContentsMargins(10, 7, 10, 7)
        self.cancel = QPushButton(tr("Cancel")); self.cancel.clicked.connect(self._close_page)
        self.cancel.setObjectName("assessmentQuietAction")
        set_button_role(self.cancel, "secondary")
        self.footer_status = QLabel(); footer_layout.addWidget(self.cancel); footer_layout.addWidget(self.footer_status)
        footer_layout.addStretch(1)
        self.back = QPushButton(tr("Back")); self.back.clicked.connect(self._back)
        self.back.setObjectName("assessmentSecondaryAction")
        set_button_role(self.back, "secondary")
        self.next = QPushButton(tr("Next")); self.next.clicked.connect(self._next)
        self.next.setObjectName("assessmentPrimaryAction")
        set_button_role(self.next, "primary")
        self.confirm = QPushButton(tr("Save revision") if edit_area_id else tr("Create Assessment Area")); self.confirm.clicked.connect(self._confirm)
        self.confirm.setObjectName("assessmentPrimaryAction")
        set_button_role(self.confirm, "primary")
        for action in (self.cancel, self.back, self.next, self.confirm): action.setMinimumHeight(32)
        footer_layout.addWidget(self.back); footer_layout.addWidget(self.next); footer_layout.addWidget(self.confirm)
        root.addWidget(self.footer)

        self.editor.workflow_state_changed.connect(self._sync_ui)
        # Compatibility for legitimate lower-level confirm_boundaries() callers.
        self.editor.area_created.connect(self.area_created)
        self.editor.area_revised.connect(self.area_created)
        self._refresh_context()
        if edit_area_id:
            self.area_name.setText(area.name)
            self.assessment_date.setDate(QDate(area.assessment_date.year, area.assessment_date.month, area.assessment_date.day))
        self._set_step(self.current_step)

    @staticmethod
    def _card(name):
        card = QFrame(); card.setObjectName(name)
        layout = QVBoxLayout(card); layout.setContentsMargins(12, 12, 12, 12); layout.setSpacing(7)
        return card

    def _build_info_card(self, layout):
        heading = QLabel(tr("Area details")); heading.setObjectName("assessmentCardTitle"); layout.addWidget(heading)
        self.area_name = QLineEdit(); self.area_name.setPlaceholderText(tr("Area name"))
        self.assessment_date = QDateEdit(QDate.currentDate()); self.assessment_date.setCalendarPopup(True)
        self.general_message = QLabel(); self.general_message.setObjectName("assessmentValidation"); self.general_message.setWordWrap(True)
        grid = QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(7)
        self._add_row(grid, 0, "Name", self.area_name)
        self._add_row(grid, 1, "Assessment date", self.assessment_date)
        layout.addLayout(grid); layout.addWidget(self.general_message)
        layout.addWidget(self._section("Context"))
        context = QGridLayout(); context.setHorizontalSpacing(8); context.setVerticalSpacing(7)
        self.domain_value = self._value(); self.dataset_value = self._value(); self.source_value = self._value()
        self._add_row(context, 0, "Domain", self.domain_value)
        self._add_row(context, 1, "Project Lines", self.dataset_value)
        self._add_row(context, 2, "Source", self.source_value)
        layout.addLayout(context)
        layout.addWidget(self._section("Geometry"))
        geometry = QGridLayout(); geometry.setHorizontalSpacing(8); geometry.setVerticalSpacing(7)
        self.elevation_value = self._value(); self.spans_value = self._value(); self.connectors_value = self._value()
        self._add_row(geometry, 0, "Elevation interval", self.elevation_value)
        self._add_row(geometry, 1, "Traced spans", self.spans_value)
        self._add_row(geometry, 2, "Connectors", self.connectors_value)
        layout.addLayout(geometry)
        layout.addWidget(self._section("Links"))
        links = QGridLayout(); links.setHorizontalSpacing(8); links.setVerticalSpacing(7)
        self.links_total_value = self._value(); self.production_value = self._value(); self.contour_value = self._value()
        self._add_row(links, 0, "Potential events", self.links_total_value)
        self._add_row(links, 1, "Production", self.production_value)
        self._add_row(links, 2, "Contour blast", self.contour_value)
        layout.addLayout(links); layout.addStretch(1)

    @staticmethod
    def _section(text):
        label = QLabel(tr(text)); label.setObjectName("assessmentSectionTitle"); return label

    @staticmethod
    def _value(text="—"):
        label = QLabel(text); label.setObjectName("assessmentFieldValue"); label.setWordWrap(True); return label

    @staticmethod
    def _add_row(grid, row, text, widget):
        label = QLabel(tr(text)); label.setObjectName("assessmentFieldLabel")
        grid.addWidget(label, row, 0); grid.addWidget(widget, row, 1)

    def _refresh_context(self):
        dataset = self.controller.state.active_dataset()
        self.domain_value.setText(self.domain_name or "—")
        self.dataset_value.setText(dataset.name if dataset else "—")
        self.source_value.setText(dataset.source_file_name if dataset else "—")

    def _start_drawing(self):
        try:
            self.editor.start_edit(self.edit_area_id) if self.edit_area_id else self.editor.start_new_area()
        except Exception as exc:
            QMessageBox.critical(self, tr("Assessment Area"),
                                 tr("Could not start boundary editing.") +
                                 f"\n\n{domain_message(str(exc))}")
        self._sync_ui()

    def _validate_general(self):
        self._refresh_context()
        if not self.area_name.text().strip():
            self.general_message.setText(tr("Name is required.")); return False
        if not self.assessment_date.date().isValid():
            self.general_message.setText(tr("Assessment date is required.")); return False
        if self.controller.state.active_dataset() is None:
            self.general_message.setText(tr("An active Project Lines dataset is required.")); return False
        self.general_message.clear(); return True

    def _next(self):
        if self.current_step == self.GENERAL:
            if self._validate_general(): self._set_step(self.BOUNDARY)
        elif self.current_step == self.BOUNDARY and self.editor.closed_boundary() is not None:
            self._update_geometry_summary(); self._run_link_preview(); self._set_step(self.REVIEW)

    def _back(self):
        if self.current_step == self.REVIEW: self._set_step(self.BOUNDARY)
        elif self.current_step == self.BOUNDARY and not self.edit_area_id: self._set_step(self.GENERAL)

    def _set_step(self, step):
        self.current_step = step; self.stepper.set_step(step)
        metadata_editable = step == self.GENERAL and not self.edit_area_id
        self.area_name.setReadOnly(not metadata_editable); self.assessment_date.setReadOnly(not metadata_editable)
        self._render_context(); self._sync_ui()

    def _update_geometry_summary(self):
        boundary = self.editor.closed_boundary()
        if boundary is None:
            for label in (self.elevation_value, self.spans_value, self.connectors_value): label.setText("—")
            return
        minimum, maximum = derive_elevation_summary(boundary)
        elevation = format_assessment_elevation_interval(minimum, maximum)
        self.elevation_value.setText(elevation)
        self.spans_value.setText(str(sum(isinstance(item, ProjectLineSpan) for item in boundary.segments)))
        self.connectors_value.setText(str(sum(isinstance(item, StraightConnector) for item in boundary.segments)))

    def _run_link_preview(self):
        self._link_preview = None; self._link_preview_error = False
        try:
            self._link_preview = self.controller.preview_assessment_event_links(self.editor.closed_boundary())
        except Exception:
            self._link_preview_error = True
        preview = self._link_preview
        self.links_total_value.setText(str(preview.total) if preview else "—")
        self.production_value.setText(str(preview.production_count) if preview else "—")
        self.contour_value.setText(str(preview.contour_count) if preview else "—")

    def _render_context(self):
        while self.context_body.count():
            item = self.context_body.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if self.current_step == self.GENERAL:
            self.context_title.setText(tr("Getting started"))
            lines = ("Enter Area details.", "Verify Domain and active Project Lines.",
                     "Continue to Boundary.")
            for text in lines: self._context_label(text)
        elif self.current_step == self.BOUNDARY:
            self.context_title.setText(tr("Boundary"))
            for text in ("Click near a Project Line to snap.", "Follow the line to trace the boundary.",
                         "Move away to create a connector.", "Close the boundary when finished."):
                self._context_label(text)
            for role, text in (("traced", "Traced Project Line"),
                               ("connector", "Connector"), ("marker", "Snap point")):
                self._legend_row(role, text)
        elif self.current_step == self.REVIEW:
            self.context_title.setText(tr("Review"))
            if self._link_preview_error:
                self._context_label("Linked-event preview unavailable")
            else:
                self._context_label("✓  General information")
                self._context_label("✓  Boundary valid")
                self._context_label("✓  Elevation summary derived")
                self._context_label("✓  Linked-event preview completed")
            self._context_row("Elevation interval", self.elevation_value.text())
            self._context_row("Traced spans", self.spans_value.text())
            self._context_row("Connectors", self.connectors_value.text())
            if self._link_preview:
                self._context_row("Total", self._link_preview.total)
                self._context_row("Production", self._link_preview.production_count)
                self._context_row("Contour blast", self._link_preview.contour_count)
                self._build_link_event_list(self._link_preview.items)

    def _build_link_event_list(self, items):
        """Keep an arbitrarily long preview inside the fixed right-hand card."""
        self.link_events_scroll = QScrollArea()
        self.link_events_scroll.setObjectName("assessmentLinkEventsScroll")
        self.link_events_scroll.setWidgetResizable(True)
        self.link_events_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.link_events_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.link_events_scroll.setSizePolicy(QSizePolicy.Policy.Preferred,
                                              QSizePolicy.Policy.Expanding)
        event_list = QWidget(); event_list.setObjectName("assessmentLinkEventsList")
        event_layout = QVBoxLayout(event_list)
        event_layout.setContentsMargins(0, 4, 0, 4); event_layout.setSpacing(4)
        self.link_event_rows = []
        for item in items:
            row = QWidget(); row.setObjectName("assessmentLinkEventRow")
            layout = QGridLayout(row); layout.setContentsMargins(2, 3, 2, 3)
            kind = tr("Production") if item.event_type == "production" else tr("Contour blast")
            type_label = QLabel(kind); type_label.setObjectName("assessmentFieldLabel")
            name_label = QLabel(item.name); name_label.setObjectName("assessmentFieldValue")
            name_label.setWordWrap(True)
            elevation = QLabel(f"{item.elevation:g} m"); elevation.setObjectName("assessmentFieldLabel")
            layout.addWidget(type_label, 0, 0); layout.addWidget(name_label, 0, 1)
            layout.addWidget(elevation, 1, 1)
            event_layout.addWidget(row); self.link_event_rows.append(row)
        event_layout.addStretch(1)
        self.link_events_scroll.setWidget(event_list)
        self.context_body.addWidget(self.link_events_scroll, 1)

    def _context_label(self, text):
        prefix = "✓  " if text.startswith("✓  ") else ""
        source = text.removeprefix("✓  ")
        label = QLabel(prefix + tr(source)); label.setWordWrap(True); self.context_body.addWidget(label)

    def _legend_row(self, role, text):
        row = QWidget(); layout = QHBoxLayout(row); layout.setContentsMargins(0, 1, 0, 1)
        swatch = QFrame(); swatch.setObjectName("GeometryLegendSwatch")
        swatch.setProperty("legendRole", role); swatch.setFixedSize(18 if role != "marker" else 8,
                                                                    3 if role != "marker" else 8)
        layout.addWidget(swatch); layout.addWidget(QLabel(tr(text))); layout.addStretch(1)
        self.context_body.addWidget(row)

    def _context_row(self, name, value):
        row = QWidget(); layout = QHBoxLayout(row); layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(tr(str(name))); label.setObjectName("assessmentFieldLabel")
        result = QLabel(str(value)); result.setObjectName("assessmentFieldValue")
        layout.addWidget(label); layout.addStretch(1); layout.addWidget(result)
        self.context_body.addWidget(row)

    def _confirm(self):
        if self._saving or self.current_step != self.REVIEW: return
        boundary = self.editor.closed_boundary()
        if boundary is None: return
        self._saving = True; self.stepper.set_step(self.SAVE); self.footer_status.setText(tr("Saving…")); self._sync_ui()
        try:
            result = self.controller.save_assessment_area_geometry(
                assessment_area_id=self.edit_area_id, name=self.area_name.text().strip(),
                assessment_date=self.assessment_date.date().toPython(), boundary=boundary)
        except Exception as exc:
            self._saving = False; self.footer_status.clear(); self.stepper.set_step(self.REVIEW); self._sync_ui()
            QMessageBox.critical(self, tr("Assessment Area"),
                                 tr("Could not save the new boundaries.") +
                                 f"\n\n{domain_message(str(exc))}")
            return
        self._saving = False
        if result.link_refresh_warning:
            QMessageBox.warning(self, tr("Assessment Area saved"),
                                tr("The Assessment Area was saved, but linked-event suggestions could not be refreshed.") + "\n\n"
                                + domain_message(result.link_refresh_warning))
        self.area_created.emit(result.area_id)

    def _close_page(self): self.cancelled.emit()

    def _sync_ui(self, *_args):
        state = self.editor.workflow_state; boundary_step = self.current_step == self.BOUNDARY
        can_edit = not self.editor.read_only and not self._saving
        self.plan_title.setText(tr(("Project plan", "Define Assessment boundary",
                                    "Assessment footprint", "Assessment footprint")[self.current_step]))
        self.start.setEnabled(can_edit and boundary_step and state == "IDLE")
        self.back_vertex.setEnabled(can_edit and boundary_step and state in {"DRAWING", "CLOSED"})
        self.finish.setEnabled(can_edit and boundary_step and state == "DRAWING")
        self.cancel_drawing.setEnabled(can_edit and boundary_step and state != "IDLE")
        drawing = boundary_step and state != "IDLE"
        self.start.setVisible(boundary_step and not drawing)
        self.back_vertex.setVisible(drawing)
        self.finish.setVisible(drawing)
        self.cancel_drawing.setVisible(drawing)
        self.editor.plan_view.set_polygon_drawing_mode(boundary_step and state == "DRAWING")
        self.back.setVisible(self.current_step != self.GENERAL)
        self.back.setEnabled(not self._saving and not (self.edit_area_id and self.current_step == self.BOUNDARY))
        self.next.setVisible(self.current_step != self.REVIEW)
        self.next.setEnabled(not self._saving and (self.current_step == self.GENERAL or
                             (boundary_step and self.editor.closed_boundary() is not None)))
        self.confirm.setVisible(self.current_step == self.REVIEW)
        self.confirm.setEnabled(can_edit and self.current_step == self.REVIEW)
        self.cancel.setEnabled(not self._saving)
        self.step_status.setText(tr({"DRAWING":"Click to draw · Wheel to zoom · Middle drag to pan",
                                     "CLOSED":"Boundary closed and valid.",
                                     "IDLE":"Inspect the plan, then use Draw boundary."}.get(state, state)))
        self._update_geometry_summary()

    def has_active_workflow(self): return self.editor.has_active_workflow()
    def cancel_active_workflow(self): return self.editor.cancel_workflow()
    def save_now(self): return None
