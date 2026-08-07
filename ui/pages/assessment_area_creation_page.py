"""Focused Area polygon workflow; the compatibility workspace acts only as a hidden controller."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox,QHBoxLayout,QLabel,QPushButton,QVBoxLayout,QWidget
from ui.pages.assessment_workspace_page import AssessmentWorkspacePage

class AssessmentAreaCreationPage(QWidget):
    area_created=Signal(str); cancelled=Signal()
    def __init__(self,context,domain_id,domain_name,site_id,parent=None,edit_area_id=None):
        super().__init__(parent); self.controller=AssessmentWorkspacePage(context,domain_id,domain_name,site_id); self.before={a.id for a in self.controller.state.assessment_areas}; self.edit_area_id=edit_area_id
        layout=QVBoxLayout(self); title="Edit Assessment Area boundaries" if edit_area_id else "Create Assessment Area"; layout.addWidget(QLabel(f"{title}\nDraw the polygon, refine boundaries, select horizons and confirm."))
        bar=QHBoxLayout(); fit=QPushButton("Fit"); fit.clicked.connect(self.controller.workspace.plan_view_fit); self.lines=QCheckBox("Project Lines"); self.lines.setChecked(self.controller.workspace.lines_checkbox.isChecked()); self.lines.toggled.connect(self._toggle_lines); self.grid=QCheckBox("Grid"); self.grid.setChecked(self.controller.workspace.grid_button.isChecked()); self.grid.toggled.connect(self._toggle_grid); back=QPushButton("Back / undo vertex"); back.clicked.connect(lambda:self._workflow_action("back")); finish=QPushButton("Finish polygon / Continue"); finish.clicked.connect(self._continue); confirm=QPushButton("Confirm boundaries"); confirm.clicked.connect(self._confirm); cancel=QPushButton("Cancel"); cancel.clicked.connect(self._cancel)
        for widget in (fit,self.lines,self.grid,back,finish,confirm,cancel):bar.addWidget(widget)
        layout.addLayout(bar); self.step_status=QLabel(); self.step_status.setWordWrap(True); layout.addWidget(self.step_status)
        self.plan=self.controller.workspace.plan_view; self.plan.setParent(self); layout.addWidget(self.plan); self.controller.state_saved.connect(self._saved)
        if edit_area_id:self.controller.open_assessment_area(edit_area_id); self.controller.workspace.edit_area_boundaries()
        else:self.controller.workspace.start_area_drawing()
        self._sync_status()
    def _saved(self):
        if self.edit_area_id:self.area_created.emit(self.edit_area_id); return
        created=[a.id for a in self.controller.state.assessment_areas if a.id not in self.before]
        if created:self.area_created.emit(created[-1])
    def _cancel(self):self.controller.cancel_active_workflow(); self.cancelled.emit()
    def _toggle_lines(self,shown):self.controller.workspace.lines_checkbox.setChecked(shown); self.controller.workspace.draw_geometry()
    def _toggle_grid(self,shown):self.controller.workspace.grid_button.setChecked(shown); self.controller.workspace.draw_geometry()
    def _workflow_action(self,key):self.controller.workspace._drawing_key(key); self._sync_status()
    def _continue(self):self.controller.workspace.finish_area_drawing(); self._sync_status()
    def _confirm(self):self.controller.workspace.confirm_refined_polygon(); self._sync_status()
    def _sync_status(self):
        state=self.controller.workspace.workflow_state; instructions={"DRAWING":"Шаг 1: добавьте вершины. Back отменяет последнюю вершину; Finish продолжает.","REFINING":"Шаг 2: уточните вершины и нажмите Confirm boundaries.","CANDIDATE_CONFIRMATION":"Шаг 3: выберите интервалы и подтвердите сохранение.","IDLE":"Готово."}; self.step_status.setText(instructions.get(state,state))
    def has_active_workflow(self):return self.controller.has_active_workflow()
    def cancel_active_workflow(self):return self.controller.cancel_active_workflow()
    def save_now(self):return self.controller.save_now()
