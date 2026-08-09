"""Focused Area polygon workflow; the compatibility workspace acts only as a hidden controller."""
from ui.presentation_labels import domain_message
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox,QHBoxLayout,QLabel,QMessageBox,QPushButton,QVBoxLayout,QWidget
from ui.pages.assessment_workspace_page import AssessmentWorkspacePage

class AssessmentAreaCreationPage(QWidget):
    area_created=Signal(str); cancelled=Signal()
    def __init__(self,context,domain_id,domain_name,site_id,parent=None,edit_area_id=None):
        super().__init__(parent); self.controller=AssessmentWorkspacePage(context,domain_id,domain_name,site_id); self.before={a.id for a in self.controller.state.assessment_areas}; self.edit_area_id=edit_area_id; self._completion_emitted=False
        layout=QVBoxLayout(self); title="Edit Assessment Area boundaries" if edit_area_id else "Create Assessment Area"; layout.addWidget(QLabel(f"{title}\nDraw the polygon, refine boundaries, select horizons and confirm."))
        bar=QHBoxLayout(); fit=QPushButton("Fit"); fit.clicked.connect(self.controller.workspace.plan_view_fit); self.lines=QCheckBox("Project Lines"); self.lines.setChecked(self.controller.workspace.lines_checkbox.isChecked()); self.lines.toggled.connect(self._toggle_lines); self.grid=QCheckBox("Grid"); self.grid.setChecked(self.controller.workspace.grid_button.isChecked()); self.grid.toggled.connect(self._toggle_grid); self.start=QPushButton("Draw boundaries"); self.start.clicked.connect(self._start_drawing); self.back_vertex=QPushButton("Undo vertex"); self.back_vertex.clicked.connect(lambda:self._workflow_action("back")); self.finish=QPushButton("Finish polygon / Continue"); self.finish.clicked.connect(self._continue); self.confirm=QPushButton("Confirm boundaries"); self.confirm.clicked.connect(self._confirm); self.cancel_drawing=QPushButton("Cancel drawing"); self.cancel_drawing.clicked.connect(self._cancel_drawing); close=QPushButton("Back / Close"); close.clicked.connect(self._close_page)
        for widget in (fit,self.lines,self.grid,self.start,self.back_vertex,self.finish,self.confirm,self.cancel_drawing,close):bar.addWidget(widget)
        layout.addLayout(bar); self.step_status=QLabel(); self.step_status.setWordWrap(True); layout.addWidget(self.step_status)
        self.plan=self.controller.workspace.plan_view; self.plan.setParent(self); layout.addWidget(self.plan)
        if edit_area_id:
            self.controller.open_assessment_area(edit_area_id); area=self._area(edit_area_id); self._edit_revision_count=len(area.geometry_revisions) if area else 0; self._edit_active_revision_id=area.active_geometry_revision_id if area else None; self.controller.workspace.edit_area_boundaries()
        else:self.controller.workspace.start_area_drawing()
        self._sync_status()
    def _area(self,area_id):return next((area for area in self.controller.state.assessment_areas if area.id==area_id),None)
    def _cancel_drawing(self): self.controller.cancel_active_workflow(); self._sync_status()
    def _close_page(self): self.cancelled.emit()
    def _start_drawing(self):
        try:
            if self.edit_area_id:
                if not self.controller.open_assessment_area(self.edit_area_id): raise ValueError("Assessment Area is not available")
                self.controller.workspace.edit_area_boundaries()
            else:self.controller.workspace.start_area_drawing()
        except Exception as exc: QMessageBox.critical(self,"Assessment Area",f"Could not start boundary editing.\n\n{domain_message(str(exc))}")
        self._sync_status()
    def _toggle_lines(self,shown):self.controller.workspace.lines_checkbox.setChecked(shown); self.controller.workspace.draw_geometry()
    def _toggle_grid(self,shown):self.controller.workspace.grid_button.setChecked(shown); self.controller.workspace.draw_geometry()
    def _workflow_action(self,key):self.controller.workspace._drawing_key(key); self._sync_status()
    def _continue(self):
        try:self.controller.workspace.finish_area_drawing()
        except Exception as exc:QMessageBox.critical(self,"Assessment Area",f"Could not start boundary refinement.\n\n{domain_message(str(exc))}")
        self._sync_status()
    def _confirm(self):
        if self._completion_emitted:return
        try:self.controller.workspace.confirm_refined_polygon()
        except Exception as exc:QMessageBox.critical(self,"Assessment Area",f"Could not save the new boundaries.\n\n{domain_message(str(exc))}")
        self._sync_status()
        if self.controller.workspace.workflow_state!="IDLE":return
        completed_id=None
        if self.edit_area_id:
            area=self._area(self.edit_area_id)
            if area and (len(area.geometry_revisions)>self._edit_revision_count or area.active_geometry_revision_id!=self._edit_active_revision_id):completed_id=self.edit_area_id
        else:
            created=[area.id for area in self.controller.state.assessment_areas if area.id not in self.before]
            if created:completed_id=created[-1]
        if completed_id:
            self._completion_emitted=True
            self.area_created.emit(completed_id)
    def _sync_status(self):
        state=self.controller.workspace.workflow_state; active=state!="IDLE"; self.start.setEnabled(not active); self.back_vertex.setEnabled(state=="DRAWING"); self.finish.setEnabled(state=="DRAWING"); self.confirm.setEnabled(state=="REFINING"); self.cancel_drawing.setEnabled(active)
        instructions={"DRAWING":"Step 1: add vertices. Undo removes the last vertex; Finish continues.","REFINING":"Step 2: refine vertices and click Confirm boundaries.","CANDIDATE_CONFIRMATION":"Step 3: select intervals and confirm.","IDLE":"Pan or zoom the plan, then click Draw boundaries."}; self.step_status.setText(instructions.get(state,state))
    def has_active_workflow(self):return self.controller.has_active_workflow()
    def cancel_active_workflow(self):return self.controller.cancel_active_workflow()
    def save_now(self):return self.controller.save_now()
