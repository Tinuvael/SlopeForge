"""Focused page for a contour BlastEvent (there is deliberately no BlastBlock)."""
from PySide6.QtWidgets import QFileDialog,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTabWidget,QVBoxLayout,QWidget
from prototype_2d.blast_event_service import BlastEventService
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.pages.technical_card_widgets import ActualExecutionEditorWidget,BlastDesignEditorWidget,TechnicalCardEditorWidget

class ContourEventPage(QWidget):
    def __init__(self,context,domain_id,domain_name,event_id,parent=None):
        super().__init__(parent); self.context=context; self.controller=EntityPageController(context,domain_id); self.event=next(e for e in self.controller.state.blast_events if e.id==event_id and e.event_type=="contour")
        root=QVBoxLayout(self); root.addWidget(QLabel(f"Contour blast: {self.event.name} | Domain: {domain_name}")); self.tabs=QTabWidget(); root.addWidget(self.tabs)
        general=QWidget(); layout=QVBoxLayout(general); rev=self.event.active_geometry_revision(); dataset=self.controller.state.active_dataset(); self.plan=PlanGeometryWidget(); self.plan.set_geometry(rev.plan_geometry if rev else None,dataset.lines if dataset else [],f"Horizon {self.event.elevation:g} | Date: {self.event.event_date or '—'} | CSV: {rev.source_file_name if rev else '—'} | Revision: {rev.revision_number if rev else '—'}"); self.plan.reimport_requested.connect(self.reimport_geometry); layout.addWidget(self.plan); self.tabs.addTab(general,"General information")
        card,draft=self.controller.technical_card_draft(self.event); self.editor=TechnicalCardEditorWidget(self.event,card,draft,self.controller.save_technical_card,self,not context.current_user.can_edit or self.event.is_archived); layout.addWidget(self.editor.take_tab("Общие"))
        self.tabs.addTab(BlastDesignEditorWidget(self.editor.take_tab("Контурное бурение")),"Blast design"); self.tabs.addTab(ActualExecutionEditorWidget(self.editor.take_tab("Факт")),"Execution fact")
        for title in ("Photos","Documents"): self.tabs.addTab(self._attachments(title),title)
        self.tabs.addTab(self.editor.take_tab("История ревизий"),"History"); actions=QHBoxLayout(); actions.addStretch(); draft_button=QPushButton("Save draft"); complete=QPushButton("Complete"); draft_button.clicked.connect(self.editor.save_draft); complete.clicked.connect(self.editor.complete); actions.addWidget(draft_button); actions.addWidget(complete); root.addLayout(actions)
    def _attachments(self,title):
        page=QWidget(); layout=QVBoxLayout(page); button=QPushButton(f"Manage {title.lower()}")
        def open_dialog():
            from ui.prototype_2d.entity_attachment_dialog import EntityAttachmentDialog
            EntityAttachmentDialog(self.controller.attachments,"blast_event",self.event.id,self,read_only=not self.context.current_user.can_edit).exec()
        button.clicked.connect(open_dialog); layout.addWidget(button); layout.addStretch(); return page
    def reimport_geometry(self):
        path,_=QFileDialog.getOpenFileName(self,"Reimport contour geometry","","CSV (*.csv)")
        if not path:return
        try: BlastEventService(self.controller.state).reimport_geometry(self.event,path); self.controller.save()
        except Exception as exc: QMessageBox.warning(self,"Contour geometry",str(exc))
