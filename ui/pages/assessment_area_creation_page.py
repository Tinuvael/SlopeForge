"""Guided Assessment Area creation and focused boundary revision page."""
from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (QCheckBox, QDateEdit, QFormLayout, QHBoxLayout, QLabel,
                              QLineEdit, QMessageBox, QPushButton, QStackedWidget,
                              QVBoxLayout, QWidget)

from app.localization import tr
from domain.assessment.geometry import (ProjectLineSpan, StraightConnector,
                                        derive_elevation_summary)
from ui.editors.assessment_geometry_editor import AssessmentGeometryEditorWidget
from ui.pages.entity_page_controller import EntityPageController
from ui.presentation_labels import domain_message


class AssessmentAreaCreationPage(QWidget):
    """A local three-step flow; persistence happens only on Review -> Save."""

    area_created = Signal(str)
    cancelled = Signal()
    GENERAL, BOUNDARY, REVIEW = range(3)

    def __init__(self, context, domain_id, domain_name, site_id, parent=None, edit_area_id=None):
        super().__init__(parent)
        self.controller = EntityPageController(context, domain_id)
        self.domain_name = domain_name
        self.edit_area_id = edit_area_id
        self._saving = False
        self.editor = AssessmentGeometryEditorWidget(
            self.controller.state, self.controller.save_assessment_area_geometry, self,
            read_only=not context.current_user.can_edit,
        )
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Edit Assessment Area boundary" if edit_area_id else "Create Assessment Area"))
        self.stepper = QLabel()
        root.addWidget(self.stepper)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        self.area_name = QLineEdit()
        self.assessment_date = QDateEdit(QDate.currentDate())
        self.assessment_date.setCalendarPopup(True)
        self.general_message = QLabel()
        self.general_message.setStyleSheet("color: #a33;")
        self.general_page = QWidget(); form = QFormLayout(self.general_page)
        form.addRow(tr("Name"), self.area_name)
        form.addRow(tr("Assessment date"), self.assessment_date)
        self.domain_value = QLabel(domain_name or "—")
        self.dataset_value = QLabel(); self.source_value = QLabel()
        form.addRow(tr("Domain"), self.domain_value)
        form.addRow(tr("Project Lines dataset"), self.dataset_value)
        form.addRow(tr("Project Lines source file"), self.source_value)
        form.addRow(self.general_message)
        self.pages.addWidget(self.general_page)

        self.boundary_page = QWidget(); self.boundary_layout = QVBoxLayout(self.boundary_page)
        controls = QHBoxLayout()
        fit = QPushButton(tr("Fit")); fit.clicked.connect(self.editor.fit_to_extent)
        self.lines = QCheckBox(tr("Project Lines")); self.lines.setChecked(True)
        self.lines.toggled.connect(self.editor.set_project_lines_visible)
        self.start = QPushButton(tr("Edit boundary") if edit_area_id else tr("Draw boundary"))
        self.start.clicked.connect(self._start_drawing)
        self.back_vertex = QPushButton(tr("Undo")); self.back_vertex.clicked.connect(self.editor.undo_vertex)
        self.finish = QPushButton(tr("Close boundary")); self.finish.clicked.connect(self.editor.finish_polygon)
        self.cancel_drawing = QPushButton(tr("Cancel drawing")); self.cancel_drawing.clicked.connect(self.editor.cancel_workflow)
        for widget in (fit, self.lines, self.start, self.back_vertex, self.finish, self.cancel_drawing):
            controls.addWidget(widget)
        self.boundary_layout.addLayout(controls)
        self.step_status = QLabel(); self.boundary_layout.addWidget(self.step_status)
        self.boundary_layout.addWidget(self.editor, 1)
        self.pages.addWidget(self.boundary_page)

        self.review_page = QWidget(); self.review_layout = QVBoxLayout(self.review_page)
        self.review_summary = QLabel(); self.review_summary.setWordWrap(True)
        self.review_layout.addWidget(self.review_summary)
        self.pages.addWidget(self.review_page)

        actions = QHBoxLayout(); actions.addStretch(1)
        self.back = QPushButton(tr("Back")); self.back.clicked.connect(self._back)
        self.next = QPushButton(tr("Next")); self.next.clicked.connect(self._next)
        self.confirm = QPushButton(tr("Save revision") if edit_area_id else tr("Save Assessment")); self.confirm.clicked.connect(self._confirm)
        close = QPushButton(tr("Back / Close")); close.clicked.connect(self._close_page)
        for widget in (self.back, self.next, self.confirm, close): actions.addWidget(widget)
        root.addLayout(actions)

        self.editor.workflow_state_changed.connect(self._sync_status)
        # Retained for legitimate lower-level callers of confirm_boundaries().
        self.editor.area_created.connect(self.area_created)
        self.editor.area_revised.connect(self.area_created)
        if edit_area_id:
            area = self.controller.area(edit_area_id)
            if area is None: raise ValueError("Assessment Area is unavailable")
            self.area_name.setText(area.name); self.area_name.setReadOnly(True)
            self.assessment_date.setDate(QDate(area.assessment_date.year, area.assessment_date.month, area.assessment_date.day))
            self.assessment_date.setReadOnly(True)
            self.editor.inspect_area(edit_area_id)
            self.pages.setCurrentIndex(self.BOUNDARY)
        else:
            self.pages.setCurrentIndex(self.GENERAL)
        self._refresh_context(); self._sync_status()

    def _refresh_context(self):
        dataset = self.controller.state.active_dataset()
        self.dataset_value.setText(dataset.name if dataset else "—")
        self.source_value.setText(dataset.source_file_name if dataset else "—")

    def _start_drawing(self):
        try:
            self.editor.start_edit(self.edit_area_id) if self.edit_area_id else self.editor.start_new_area()
        except Exception as exc:
            QMessageBox.critical(self, tr("Assessment Area"), f"Could not start boundary editing.\n\n{domain_message(str(exc))}")
        self._sync_status()

    def _next(self):
        if self.pages.currentIndex() == self.GENERAL:
            self._refresh_context()
            if not self.area_name.text().strip():
                self.general_message.setText("Enter an Assessment Area name."); return
            if not self.assessment_date.date().isValid():
                self.general_message.setText("Select an Assessment date."); return
            if self.controller.state.active_dataset() is None:
                self.general_message.setText("An active Project Lines dataset is required."); return
            self.general_message.clear(); self._show_boundary()
        elif self.pages.currentIndex() == self.BOUNDARY and self.editor.closed_boundary() is not None:
            self._populate_review(); self.review_layout.addWidget(self.editor, 1); self.pages.setCurrentIndex(self.REVIEW)
        self._sync_status()

    def _back(self):
        current = self.pages.currentIndex()
        if current == self.REVIEW: self._show_boundary()
        elif current == self.BOUNDARY and not self.edit_area_id: self.pages.setCurrentIndex(self.GENERAL)
        self._sync_status()

    def _show_boundary(self):
        """Reuse the same renderer so Review never owns a duplicate geometry model."""
        self.boundary_layout.addWidget(self.editor, 1)
        self.pages.setCurrentIndex(self.BOUNDARY)

    @staticmethod
    def _elevation_text(value):
        return "—" if value is None else f"{value:g}"

    def _populate_review(self):
        boundary = self.editor.closed_boundary()
        minimum, maximum = derive_elevation_summary(boundary)
        dataset = self.controller.state.active_dataset()
        spans = sum(isinstance(segment, ProjectLineSpan) for segment in boundary.segments)
        connectors = sum(isinstance(segment, StraightConnector) for segment in boundary.segments)
        self.review_summary.setText(
            f"Name: {self.area_name.text().strip()}\nAssessment date: {self.assessment_date.date().toString('yyyy-MM-dd')}\n"
            f"Domain: {self.domain_name or '—'}\nProject Lines dataset: {dataset.name if dataset else '—'}\n"
            f"Project Lines source file: {dataset.source_file_name if dataset else '—'}\n"
            f"Elevation Interval: {self._elevation_text(minimum)} – {self._elevation_text(maximum)}\n"
            f"Project-Line spans: {spans}\nStraight connectors: {connectors}")

    def _confirm(self):
        if self._saving: return
        boundary = self.editor.closed_boundary()
        if self.pages.currentIndex() != self.REVIEW or boundary is None: return
        self._saving = True; self._sync_status()
        try:
            result = self.controller.save_assessment_area_geometry(
                assessment_area_id=self.edit_area_id, name=self.area_name.text().strip(),
                assessment_date=self.assessment_date.date().toPython(), boundary=boundary)
        except Exception as exc:
            QMessageBox.critical(self, tr("Assessment Area"), f"Could not save the new boundaries.\n\n{domain_message(str(exc))}")
            return
        finally:
            self._saving = False; self._sync_status()
        if result.link_refresh_warning:
            QMessageBox.warning(self, tr("Assessment Area saved"),
                                "The Assessment Area was saved, but linked-event suggestions could not be refreshed.\n\n"
                                + domain_message(result.link_refresh_warning))
        self.area_created.emit(result.area_id)

    def _close_page(self): self.cancelled.emit()

    def _sync_status(self, *_args):
        state = self.editor.workflow_state; current = self.pages.currentIndex()
        can_edit = not self.editor.read_only
        self.start.setEnabled(can_edit and state == "IDLE")
        self.back_vertex.setEnabled(can_edit and state in {"DRAWING", "CLOSED"})
        self.finish.setEnabled(can_edit and state == "DRAWING")
        self.cancel_drawing.setEnabled(can_edit and state != "IDLE")
        self.back.setEnabled(current == self.REVIEW or (current == self.BOUNDARY and not self.edit_area_id))
        self.next.setVisible(current != self.REVIEW)
        self.next.setEnabled(current == self.GENERAL or (current == self.BOUNDARY and self.editor.closed_boundary() is not None))
        self.confirm.setVisible(current == self.REVIEW and can_edit)
        self.confirm.setEnabled(current == self.REVIEW and not self._saving)
        names = ("General information", "Boundary", "Review")
        self.stepper.setText("  →  ".join(f"[{name}]" if i == current else name for i, name in enumerate(names)))
        self.step_status.setText({"DRAWING":"Wheel: zoom · Middle drag: pan · Click: draw. Close boundary when finished.",
                                  "CLOSED":"Boundary closed and valid. Continue to Review or use Undo to edit it.",
                                  "IDLE":"Wheel: zoom · Middle drag: pan. Inspect the plan, then start boundary drawing."}.get(state, state))

    def has_active_workflow(self): return self.editor.has_active_workflow()
    def cancel_active_workflow(self): return self.editor.cancel_workflow()
    def save_now(self): return None
