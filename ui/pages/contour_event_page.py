"""Focused page for a contour BlastEvent (there is deliberately no BlastBlock)."""
from ui.presentation_labels import domain_message
from PySide6.QtWidgets import QFileDialog,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTabWidget,QVBoxLayout,QWidget
from prototype_2d.blast_event_service import BlastEventService
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.pages.technical_card_widgets import ActualExecutionEditorWidget,BlastDesignEditorWidget,TechnicalCardEditorWidget

class ContourEventPage(QWidget):
    def __init__(self,context,domain_id,domain_name,event_id,parent=None):
        super().__init__(parent); self.context=context; self.controller=EntityPageController(context,domain_id); self.blast_event=next(e for e in self.controller.state.blast_events if e.id==event_id and e.event_type=="contour"); self.read_only=not context.current_user.can_edit or self.blast_event.is_archived
        root=QVBoxLayout(self); root.addWidget(QLabel(f"Contour blast: {self.blast_event.name} | Domain: {domain_name}")); self.tabs=QTabWidget(); root.addWidget(self.tabs)
        general=QWidget(); layout=QVBoxLayout(general); rev=self.blast_event.active_geometry_revision(); dataset=self.controller.state.active_dataset(); self.plan=PlanGeometryWidget(); self.plan.set_geometry(rev.plan_geometry if rev else None,dataset.lines if dataset else [],f"Horizon {self.blast_event.elevation:g} | Date: {self.blast_event.event_date or '—'} | CSV: {rev.source_file_name if rev else '—'} | Revision: {rev.revision_number if rev else '—'}"); self.plan.set_reimport_enabled(not self.read_only); self.plan.reimport_requested.connect(self.reimport_geometry); layout.addWidget(self.plan); self.tabs.addTab(general,"General information")
        card,draft=self.controller.technical_card_draft(self.blast_event); self.editor=TechnicalCardEditorWidget(self.blast_event,card,draft,self.controller.save_technical_card,self,self.read_only); layout.addWidget(self.editor.take_tab("General"))
        self.tabs.addTab(BlastDesignEditorWidget(self.editor.take_tab("Contour drilling")),"Blast design"); self.tabs.addTab(ActualExecutionEditorWidget(self.editor.take_tab("Execution fact")),"Execution fact")
        for title in ("Photos","Documents"): self.tabs.addTab(self._attachments(title),title)
        self.tabs.addTab(self.editor.take_tab("Revision history"),"History"); actions=QHBoxLayout(); actions.addStretch(); self.draft_button=QPushButton("Save draft"); self.complete_button=QPushButton("Complete"); self.draft_button.setEnabled(not self.read_only); self.complete_button.setEnabled(not self.read_only); self.draft_button.clicked.connect(self.save_draft); self.complete_button.clicked.connect(self.complete); actions.addWidget(self.draft_button); actions.addWidget(self.complete_button); root.addLayout(actions)
    def _attachments(self,title):
        page=QWidget(); layout=QVBoxLayout(page); button=QPushButton(f"Manage {title.lower()}")
        def open_dialog():
            from ui.dialogs.entity_attachment_dialog import EntityAttachmentDialog
            EntityAttachmentDialog(self.controller.attachments,"blast_event",self.blast_event.id,self,read_only=self.read_only).exec()
        button.clicked.connect(open_dialog); layout.addWidget(button); layout.addStretch(); return page
    def reimport_geometry(self):
        if self.read_only: QMessageBox.warning(self,"Read only","Archived contour events and Viewer accounts are read-only."); return
        path,_=QFileDialog.getOpenFileName(self,"Reimport contour geometry","","CSV (*.csv)")
        if not path:return
        try: BlastEventService(self.controller.state).reimport_geometry(self.blast_event,path); self.controller.save()
        except Exception as exc: QMessageBox.warning(self,"Contour geometry",domain_message(str(exc)))
    def save_draft(self):
        if self.read_only: QMessageBox.warning(self,"Read only","This contour event is read-only."); return False
        return self.editor.save_draft()
    def complete(self):
        if self.read_only: QMessageBox.warning(self,"Read only","This contour event is read-only."); return False
        return self.editor.complete()
