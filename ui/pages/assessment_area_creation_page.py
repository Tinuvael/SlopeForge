"""Focused Area polygon workflow; the compatibility workspace acts only as a hidden controller."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel,QPushButton,QVBoxLayout,QWidget
from ui.pages.assessment_workspace_page import AssessmentWorkspacePage

class AssessmentAreaCreationPage(QWidget):
    area_created=Signal(str); cancelled=Signal()
    def __init__(self,context,domain_id,domain_name,site_id,parent=None,edit_area_id=None):
        super().__init__(parent); self.controller=AssessmentWorkspacePage(context,domain_id,domain_name,site_id); self.before={a.id for a in self.controller.state.assessment_areas}; self.edit_area_id=edit_area_id
        layout=QVBoxLayout(self); title="Edit Assessment Area boundaries" if edit_area_id else "Create Assessment Area"; layout.addWidget(QLabel(f"{title}\nDraw the polygon, refine boundaries, select horizons and confirm."))
        self.plan=self.controller.workspace.plan_view; self.plan.setParent(self); layout.addWidget(self.plan); cancel=QPushButton("Cancel"); cancel.clicked.connect(self._cancel); layout.addWidget(cancel); self.controller.state_saved.connect(self._saved)
        if edit_area_id:self.controller.open_assessment_area(edit_area_id); self.controller.workspace.edit_area_boundaries()
        else:self.controller.workspace.start_area_drawing()
    def _saved(self):
        if self.edit_area_id:self.area_created.emit(self.edit_area_id); return
        created=[a.id for a in self.controller.state.assessment_areas if a.id not in self.before]
        if created:self.area_created.emit(created[-1])
    def _cancel(self):self.controller.cancel_active_workflow(); self.cancelled.emit()
    def has_active_workflow(self):return self.controller.has_active_workflow()
    def cancel_active_workflow(self):return self.controller.cancel_active_workflow()
    def save_now(self):return self.controller.save_now()
