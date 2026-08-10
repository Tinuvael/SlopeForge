from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

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
        layout.addWidget(QLabel(f"{title}\nDraw the polygon, refine boundaries, select horizons and confirm."))
        bar = QHBoxLayout()
        fit = QPushButton(tr("Fit")); fit.clicked.connect(self.editor.fit_to_extent)
        self.lines = QCheckBox(tr("Project Lines")); self.lines.setChecked(True)
        self.lines.toggled.connect(self.editor.set_project_lines_visible)
        self.grid = QCheckBox(tr("Grid")); self.grid.setChecked(True)
        self.grid.toggled.connect(self.editor.set_grid_visible)
        self.start = QPushButton(tr("Draw boundaries")); self.start.clicked.connect(self._start_drawing)
        self.back_vertex = QPushButton(tr("Undo vertex")); self.back_vertex.clicked.connect(self.editor.undo_vertex)
        self.finish = QPushButton(tr("Finish polygon / Continue")); self.finish.clicked.connect(self.editor.finish_polygon)
        self.confirm = QPushButton(tr("Confirm boundaries")); self.confirm.clicked.connect(self._confirm)
        self.cancel_drawing = QPushButton(tr("Cancel drawing")); self.cancel_drawing.clicked.connect(self.editor.cancel_workflow)
        close = QPushButton(tr("Back / Close")); close.clicked.connect(self._close_page)
        for widget in (fit, self.lines, self.grid, self.start, self.back_vertex, self.finish,
                       self.confirm, self.cancel_drawing, close):
            bar.addWidget(widget)
        layout.addLayout(bar)
        self.step_status = QLabel(); self.step_status.setWordWrap(True); layout.addWidget(self.step_status)
        layout.addWidget(self.editor, 1)
        self.editor.workflow_state_changed.connect(self._sync_status)
        self.editor.area_created.connect(self.area_created)
        self.editor.area_revised.connect(self.area_created)
        self._start_drawing()

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
            self.editor.confirm_boundaries()
        except Exception as exc:
            QMessageBox.critical(self, tr("Assessment Area"),
                                 f"Could not save the new boundaries.\n\n{domain_message(str(exc))}")
        self._sync_status()

    def _close_page(self):
        self.cancelled.emit()

    def _sync_status(self, *_args):
        state = self.editor.workflow_state
        active = state != "IDLE"
        self.start.setEnabled(not active)
        self.back_vertex.setEnabled(state == "DRAWING")
        self.finish.setEnabled(state == "DRAWING")
        self.confirm.setEnabled(state == "REFINING")
        self.cancel_drawing.setEnabled(active)
        instructions = {
            "DRAWING": "Step 1: add vertices. Undo removes the last vertex; Finish continues.",
            "REFINING": "Step 2: refine vertices and click Confirm boundaries.",
            "CANDIDATE_CONFIRMATION": "Step 3: select intervals and confirm.",
            "IDLE": "Pan or zoom the plan, then click Draw boundaries.",
        }
        self.step_status.setText(instructions.get(state, state))

    def has_active_workflow(self):
        return self.editor.has_active_workflow()

    def cancel_active_workflow(self):
        return self.editor.cancel_workflow()

    def save_now(self):
        if self.controller.context.current_user.can_edit:
            self.controller.save()
