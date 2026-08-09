"""Normal entity page for one Assessment Area (the legacy workspace is not shown)."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QHBoxLayout,QInputDialog,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,
                               QTabWidget,QVBoxLayout,QWidget)
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.editors.assessment_evaluation_editor import AssessmentAreaEvaluationDialog

class AssessmentAreaPage(QWidget):
    edit_boundaries_requested=Signal(str)
    def __init__(self,context,domain_id,domain_name,area_id,parent=None):
        super().__init__(parent); self.context=context; self.domain_id=domain_id; self.domain_name=domain_name; self.area_id=area_id; self.controller=EntityPageController(context,domain_id); self.area=self.controller.area(area_id); self.read_only=not context.current_user.can_edit or self.area.is_archived
        root=QVBoxLayout(self); self.title=QLabel(self.area.name); self.title.setStyleSheet("font-size:24px;font-weight:700"); root.addWidget(self.title); self.tabs=QTabWidget(); root.addWidget(self.tabs)
        self._overview(); self._assessment(); self._linked_events(); self._attachment_tab("Photos"); self._attachment_tab("Documents"); self.tabs.addTab(self.history,"History")
    def _overview(self):
        page=QWidget(); layout=QVBoxLayout(page); rev=self.area.active_geometry_revision(); meta=QLabel(f"Domain: {self.domain_name} | Elevation: {rev.lower_elevation:g}–{rev.upper_elevation:g} | Date: {self.area.assessment_date} | Geometry revision: {rev.revision_number} | Dataset: {rev.source_dataset_id}"); meta.setWordWrap(True); layout.addWidget(meta)
        self.plan=PlanGeometryWidget(); dataset=next((d for d in self.controller.state.datasets if d.id==rev.source_dataset_id),None); self.plan.set_geometry(rev.final_geometry_frozen,dataset.lines if dataset else [],f"Interval {rev.lower_elevation:g}–{rev.upper_elevation:g}"); layout.addWidget(self.plan)
        self.edit_boundaries_button=QPushButton("Edit boundaries"); self.edit_boundaries_button.setEnabled(not self.read_only); self.edit_boundaries_button.clicked.connect(self._request_edit_boundaries); layout.addWidget(self.edit_boundaries_button); self.tabs.addTab(page,"Overview")
    def _assessment(self):
        evaluation,draft=self.controller.evaluation_draft(self.area); self.evaluation=evaluation
        self.evaluation_editor=AssessmentAreaEvaluationDialog(self.area,evaluation,draft,self.controller.save_evaluation,None,read_only=self.read_only)
        source=self.evaluation_editor.tabs
        def take(title):
            for i in range(source.count()):
                if source.tabText(i)==title: page=source.widget(i); source.removeTab(i); return page
            return QWidget()
        assessment=QWidget(); layout=QVBoxLayout(assessment); self.assessment_sections=QTabWidget(); self.assessment_sections.addTab(take("General"),"General"); self.assessment_sections.addTab(take("Geometry"),"Geometry"); self.assessment_sections.addTab(take("Face condition"),"Face condition"); layout.addWidget(self.assessment_sections); controls=QHBoxLayout(); self.save_evaluation_button=QPushButton("Save draft"); self.complete_evaluation_button=QPushButton("Complete assessment"); self.save_evaluation_button.setEnabled(not self.read_only); self.complete_evaluation_button.setEnabled(not self.read_only); self.save_evaluation_button.clicked.connect(lambda:self._save_evaluation("draft")); self.complete_evaluation_button.clicked.connect(lambda:self._save_evaluation("completed")); controls.addStretch(); controls.addWidget(self.save_evaluation_button); controls.addWidget(self.complete_evaluation_button); layout.addLayout(controls); self.tabs.addTab(assessment,"Assessment")
        self.result=take("Matrix"); self.tabs.addTab(self.result,"Result"); self.history=take("History")
    def _linked_events(self):
        page=QWidget(); layout=QVBoxLayout(page); self.links_table=QTableWidget(0,8); self.links_table.setHorizontalHeaderLabels(["Status","Source","BlastEvent","Type","Elevation","Revision","State","Spatial match"]); layout.addWidget(self.links_table)
        actions=QHBoxLayout();
        for label,callback in (("Confirm",self.confirm_link),("Exclude",self.exclude_link),("Restore suggestion",self.restore_link),("Add manually",self.add_manual_link),("Recalculate links",self.recalculate_links),("Show on plan",self.show_link_on_plan)):
            button=QPushButton(label); button.setEnabled(label=="Show on plan" or not self.read_only); button.clicked.connect(callback); actions.addWidget(button)
        layout.addLayout(actions); self.tabs.addTab(page,"Linked events"); self.refresh_links()
    def refresh_links(self):
        links=self.area.links_for_revision(); self.links_table.setRowCount(len(links))
        for row,link in enumerate(links):
            event=self.controller.links.event(link.blast_event_id); candidate=self.controller.links.evaluate_event(self.area,event); values=(link.status,link.source,event.name,event.event_type,f"{event.elevation:g}",link.geometry_revision_id,"stale" if self.controller.links.is_stale(link) else "current","yes" if candidate.spatial_matches else "no")
            for col,value in enumerate(values):self.links_table.setItem(row,col,QTableWidgetItem(value))
    def _selected_link(self):
        row=self.links_table.currentRow(); links=self.area.links_for_revision(); return links[row] if 0<=row<len(links) else None
    def _change_link(self,method):
        if not self._ensure_editable():return
        link=self._selected_link()
        if link:method(self.area,link.id); self.controller.save(); self.refresh_links()
    def confirm_link(self):self._change_link(self.controller.links.confirm_link)
    def exclude_link(self):self._change_link(self.controller.links.exclude_link)
    def restore_link(self):self._change_link(self.controller.links.restore_suggestion)
    def recalculate_links(self):
        if not self._ensure_editable():return
        self.controller.links.refresh_suggestions(self.area); self.controller.save(); self.refresh_links()
    def add_manual_link(self):
        if not self._ensure_editable():return
        events=[e for e in self.controller.state.blast_events if not e.is_archived]
        labels=[f"{e.name} ({e.event_type}, {e.elevation:g})" for e in events]; selected,ok=QInputDialog.getItem(self,"Add linked event","BlastEvent",labels,0,False)
        if ok and selected:self.controller.links.add_manual_link(self.area,events[labels.index(selected)].id); self.controller.save(); self.refresh_links()
    def show_link_on_plan(self):
        link=self._selected_link()
        if not link:return
        event=self.controller.links.event(link.blast_event_id); revision=event.active_geometry_revision(); area_revision=self.area.active_geometry_revision(); dataset=next((d for d in self.controller.state.datasets if d.id==area_revision.source_dataset_id),None)
        self.plan.set_geometry(revision.plan_geometry if revision else area_revision.final_geometry_frozen,dataset.lines if dataset else [],f"{event.name} | {event.elevation:g}"); self.tabs.setCurrentIndex(0)
    def _attachment_tab(self,title):
        kind="photo" if title=="Photos" else "document"
        page=QWidget(); layout=QVBoxLayout(page); hint=QLabel(); manage=QPushButton(f"Manage {title.lower()}"); self.attachment_controls=getattr(self,"attachment_controls",[]); self.attachment_controls.append((kind,manage,hint)); layout.addWidget(hint)
        def open_dialog():
            from ui.dialogs.entity_attachment_dialog import EntityAttachmentDialog
            self.evaluation=self.controller.ensure_evaluation_owner(self.area,self.evaluation)
            dialog=EntityAttachmentDialog(self.controller.attachments,"assessment_evaluation",self.evaluation.id,self,read_only=self.read_only)
            dialog.tabs.setCurrentIndex(0 if kind=="photo" else 1); dialog.exec(); self._refresh_attachment_controls()
        manage.clicked.connect(open_dialog); layout.addWidget(manage); layout.addStretch(); self.tabs.addTab(page,title); self._refresh_attachment_controls()
    def _save_evaluation(self,status):
        if not self._ensure_editable():return
        if self.evaluation_editor.save(status): self._refresh_attachment_controls()
    def _refresh_attachment_controls(self):
        persisted=self.evaluation in self.controller.state.evaluations
        for kind,button,hint in getattr(self,"attachment_controls",[]):
            count=len(self.controller.attachments.list_for_owner("assessment_evaluation",self.evaluation.id,kind)) if persisted else 0
            button.setEnabled(not self.read_only or persisted)
            hint.setText(f"{count} {'photo' if kind=='photo' else 'document'}{'s' if count!=1 else ''}" if count else ("No photos yet" if kind=="photo" else "No documents yet"))
    def _ensure_editable(self):
        if self.read_only: QMessageBox.warning(self,"Read only","Archived Assessment Areas and Viewer accounts are read-only."); return False
        return True
    def _request_edit_boundaries(self):
        if self._ensure_editable():self.edit_boundaries_requested.emit(self.area.id)
