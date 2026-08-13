from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (QCheckBox, QDateEdit, QFormLayout, QHBoxLayout, QLabel,
                              QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from app.localization import tr
from ui.editors.assessment_geometry_editor import AssessmentGeometryEditorWidget
from ui.pages.entity_page_controller import EntityPageController
from ui.presentation_labels import domain_message


class AssessmentAreaCreationPage(QWidget):
    """Production page that composes the focused geometry editor directly."""

    area_created = Signal(str)
    cancelled = Signal()

    def __init__(self, context, domain_id, domain_name, site_id, parent=None, edit_area_id=None):
        super().__init__(parent)
        self.controller = EntityPageController(context, domain_id)
        self.edit_area_id = edit_area_id
        self.editor = AssessmentGeometryEditorWidget(
            self.controller.state, self.controller.save_assessment_area_geometry, self,
            read_only=not context.current_user.can_edit,
        )
        layout = QVBoxLayout(self)
        title = "Edit Assessment Area boundaries" if edit_area_id else "Create Assessment Area"
        layout.addWidget(QLabel(f"{title}\nDraw one continuous boundary by tracing Project Lines and adding straight connectors."))
        metadata = QFormLayout()
        self.area_name = QLineEdit()
        self.assessment_date = QDateEdit(QDate.currentDate()); self.assessment_date.setCalendarPopup(True)
        if edit_area_id:
            area = self.controller.area(edit_area_id)
            if area is None: raise ValueError("Assessment Area is unavailable")
            self.area_name.setText(area.name); self.area_name.setReadOnly(True)
            self.assessment_date.setDate(QDate(area.assessment_date.year, area.assessment_date.month, area.assessment_date.day))
            self.assessment_date.setReadOnly(True)
        metadata.addRow(tr("Name"), self.area_name)
        metadata.addRow(tr("Assessment date"), self.assessment_date)
        layout.addLayout(metadata)
        bar = QHBoxLayout()
        fit = QPushButton(tr("Fit")); fit.clicked.connect(self.editor.fit_to_extent)
        self.lines = QCheckBox(tr("Project Lines")); self.lines.setChecked(True)
        self.lines.toggled.connect(self.editor.set_project_lines_visible)
        self.start = QPushButton(tr("Edit boundary") if edit_area_id else tr("Draw boundary")); self.start.clicked.connect(self._start_drawing)
        self.back_vertex = QPushButton(tr("Undo")); self.back_vertex.clicked.connect(self.editor.undo_vertex)
        self.finish = QPushButton(tr("Close boundary")); self.finish.clicked.connect(self.editor.finish_polygon)
        self.confirm = QPushButton(tr("Save Assessment")); self.confirm.clicked.connect(self._confirm)
        self.cancel_drawing = QPushButton(tr("Cancel drawing")); self.cancel_drawing.clicked.connect(self.editor.cancel_workflow)
        close = QPushButton(tr("Back / Close")); close.clicked.connect(self._close_page)
        for widget in (fit, self.lines, self.start, self.back_vertex, self.finish,
                       self.confirm, self.cancel_drawing, close):
            bar.addWidget(widget)
        layout.addLayout(bar)
        self.step_status = QLabel(); self.step_status.setWordWrap(True); layout.addWidget(self.step_status)
        layout.addWidget(self.editor, 1)
        self.editor.workflow_state_changed.connect(self._sync_status)
        self.editor.area_created.connect(self.area_created)
        self.editor.area_revised.connect(self.area_created)
        if edit_area_id:
            self.editor.inspect_area(edit_area_id)
        self._sync_status()

    def _start_drawing(self):
        try:
            if self.edit_area_id:
                self.editor.start_edit(self.edit_area_id)
            else:
                self.editor.start_new_area()
        except Exception as exc:
            QMessageBox.critical(self, tr("Assessment Area"),
                                 f"Could not start boundary editing.\n\n{domain_message(str(exc))}")
        self._sync_status()

    def _confirm(self):
        try:
            self.editor.confirm_boundaries(name=self.area_name.text(),
                                           assessment_date=self.assessment_date.date().toPython())
        except Exception as exc:
            QMessageBox.critical(self, tr("Assessment Area"),
                                 f"Could not save the new boundaries.\n\n{domain_message(str(exc))}")
        self._sync_status()

    def _close_page(self):
        self.cancelled.emit()

    def _sync_status(self, *_args):
        state = self.editor.workflow_state
        self.start.setEnabled(state == "IDLE")
        self.back_vertex.setEnabled(state in {"DRAWING", "CLOSED"})
        self.finish.setEnabled(state == "DRAWING")
        self.confirm.setEnabled(state == "CLOSED")
        self.cancel_drawing.setEnabled(state != "IDLE")
        instructions = {
            "DRAWING": "Wheel: zoom · Middle drag: pan · Click: draw. Close boundary when finished.",
            "CLOSED": "Boundary closed and valid. Save Assessment or use Undo to edit it.",
            "IDLE": "Wheel: zoom · Middle drag: pan. Inspect the plan, then start boundary drawing.",
        }
        self.step_status.setText(instructions.get(state, state))

    def has_active_workflow(self):
        return self.editor.has_active_workflow()

    def cancel_active_workflow(self):
        return self.editor.cancel_workflow()

    def save_now(self):
        """Leave-guard hook; confirmed geometry is already persisted atomically."""
        return None
