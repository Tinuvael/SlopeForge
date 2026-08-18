from app.localization import tr
"""Focused Block-style page for one contour BlastEvent (never a BlastBlock)."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog,QGridLayout,QHBoxLayout,QLabel,QMessageBox,QPushButton,QVBoxLayout,QWidget
from repositories.entity_history_repository import EntityHistoryRepository
from ui.pages.entity_history_widget import EntityHistoryWidget
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.entity_tabs import create_attachment_tab_page, create_entity_tabs
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.pages.block_card_widgets import AttachmentPreviewWidget,CardFrame,apply_workflow_badge_style
from ui.pages.technical_card_widgets import ActualExecutionEditorWidget,BlastDesignEditorWidget,TechnicalCardEditorWidget
from ui.presentation_labels import domain_message
from domain.blasting.workflow import WORKFLOW_LABELS, blast_workflow_for


def _show(value,unit=""):return "—" if value in (None,"") else f"{value:g}{unit}" if isinstance(value,(int,float)) else str(value)

class ContourEventPage(QWidget):
    metadata_saved=Signal(str,int)
    def __init__(self,context,domain_id,domain_name,event_id,parent=None):
        super().__init__(parent); self.context=context; self.domain_name=domain_name; self.controller=EntityPageController(context,domain_id); self.history_repo=EntityHistoryRepository(context.session_factory); self.blast_event=next(e for e in self.controller.state.blast_events if e.id==event_id and e.event_type=="contour"); self.read_only=not context.current_user.can_edit or self.blast_event.is_archived; self.rev=self.blast_event.active_geometry_revision()
        from app.use_case_factory import create_charge_presets,create_explosive_catalogue
        card,draft=self.controller.technical_card_draft(self.blast_event); self.card,self.draft=card,draft; self.editor=TechnicalCardEditorWidget(self.blast_event,card,draft,self.controller.save_technical_card,self,self.read_only,
            explosive_products=create_explosive_catalogue(context).list_enabled_products(),charge_presets=create_charge_presets(context,self.controller.site_id))
        root=QVBoxLayout(self); self._header(root); body=QHBoxLayout(); left=QVBoxLayout(); self.tabs=create_entity_tabs(); left.addWidget(self.tabs)
        self.engineering_actions_widget=QWidget(); actions=QHBoxLayout(self.engineering_actions_widget); actions.setContentsMargins(0,0,0,0); actions.addStretch(); self.draft_button=QPushButton(tr("Save draft")); self.complete_button=QPushButton(tr("Complete")); self.draft_button.setEnabled(not self.read_only); self.complete_button.setEnabled(not self.read_only); self.draft_button.clicked.connect(self.save_draft); self.complete_button.clicked.connect(self.complete); actions.addWidget(self.draft_button); actions.addWidget(self.complete_button); left.addWidget(self.engineering_actions_widget); body.addLayout(left,4); self._sidebar(body); root.addLayout(body)
        self._general(); self.tabs.addTab(BlastDesignEditorWidget(self.editor.take_tab(tr("Contour drilling"))),tr("Blast design")); self.tabs.addTab(ActualExecutionEditorWidget(self.editor.take_tab(tr("Execution fact"))),tr("Execution fact")); self.photos_tab=self._attachments("Photos"); self.documents_tab=self._attachments("Documents"); self.tabs.addTab(self.photos_tab,tr("Photos")); self.tabs.addTab(self.documents_tab,tr("Documents")); self.history=EntityHistoryWidget(); self.tabs.addTab(self.history,tr("History")); self.tabs.currentChanged.connect(self._sync_engineering_actions_visibility); self._sync_engineering_actions_visibility(); self._refresh_sidebar(); self._refresh_history()
        self.setStyleSheet("#CardFrame{background:white;border:1px solid #dfe3ea;border-radius:8px} #CardTitle{font-weight:600;color:#111827} #EntityTitle{font-size:24px;font-weight:700} #StatusBadge{background:#fff4d6;color:#8a5a00;border:1px solid #f4c76b;border-radius:5px;padding:4px 8px} #MetaBadge{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:5px;padding:4px 8px} #MutedText{color:#6b7280}")
    def _sync_engineering_actions_visibility(self,*_args):
        self.engineering_actions_widget.setVisible(self.tabs.currentIndex() in (1,2))
    def _header(self,root):
        card=CardFrame(); top=QHBoxLayout(); title=QLabel(f"{tr('Contour blast')} {self.blast_event.name}"); title.setObjectName("EntityTitle"); self.header_status=QLabel(); apply_workflow_badge_style(self.header_status); top.addWidget(title); top.addWidget(self.header_status)
        if self.blast_event.is_archived: top.addWidget(QLabel(tr("Archived")))
        top.addStretch(); self.edit_button=QPushButton(tr("Edit")); self.edit_button.setEnabled(not self.read_only); self.edit_button.clicked.connect(self.edit_metadata); top.addWidget(self.edit_button)
        card.layout.addLayout(top); meta=QHBoxLayout()
        for index,text in enumerate((f"{tr('ID')}: {self.blast_event.id}",f"{tr('Horizon')}: {self.blast_event.elevation:g} m",f"{tr('Domain')}: {self.domain_name}",f"{tr('Planned blast date')}: {self.blast_event.event_date or '—'}",f"{tr('Revision')}: {self.rev.revision_number if self.rev else '—'}")):
            badge=QLabel(text); badge.setObjectName("MetaBadge"); meta.addWidget(badge)
            if index == 3: self.header_date = badge
        meta.addStretch(); card.layout.addLayout(meta); root.addWidget(card)
        self._refresh_workflow_presentation()

    def edit_metadata(self):
        from repositories.domain_repository import DomainRepository
        from ui.dialogs.entity_metadata_dialogs import ContourMetadataDialog
        repo=DomainRepository(self.context.session_factory); domains=repo.selectable_for_site(self.controller.site_id)
        dialog=ContourMetadataDialog(domains,self.controller.domain_id,self.blast_event.name,self.blast_event.elevation,self)
        if not dialog.exec(): return
        name=dialog.name.text().strip(); target_id,target_version=dialog.selected_domain
        if not name: QMessageBox.warning(self,tr("Could not save"),tr("Name is required")); return
        if self.rev and abs(dialog.horizon.value()-float(self.rev.elevation))>0.01:
            text=tr("The new Horizon differs from the active imported geometry elevation. Existing geometry revisions will remain unchanged.\n\nContinue?")
            if QMessageBox.question(self,tr("Frozen geometry"),text)!=QMessageBox.Yes:return
        try:self.controller.update_contour_metadata(self.blast_event,name=name,elevation=dialog.horizon.value(),target_domain_id=target_id,target_expected_version=target_version)
        except Exception as exc:QMessageBox.warning(self,tr("Could not save"),domain_message(str(exc))); return
        self.metadata_saved.emit(self.blast_event.id,target_id)

    def _refresh_workflow_presentation(self):
        workflow = tr(WORKFLOW_LABELS[blast_workflow_for(self.controller.state, self.blast_event)])
        planned = self.blast_event.event_date or "—"
        self.header_status.setText(workflow)
        self.header_date.setText(f"{tr('Planned blast date')}: {planned}")
        if hasattr(self, "general_information"):
            self.general_information["Status"].setText(workflow)
            self.general_information["Planned blast date"].setText(str(planned))
    def _sidebar(self,body):
        right=QVBoxLayout(); self.summary=CardFrame("Summary"); self.summary_grid=QGridLayout(); self.summary.layout.addLayout(self.summary_grid); right.addWidget(self.summary); self.photo_preview=AttachmentPreviewWidget("Photos"); self.document_preview=AttachmentPreviewWidget("Documents"); self.photo_preview.add_button.clicked.connect(lambda:self.tabs.setCurrentWidget(self.photos_tab)); self.document_preview.add_button.clicked.connect(lambda:self.tabs.setCurrentWidget(self.documents_tab)); right.addWidget(self.photo_preview); right.addWidget(self.document_preview); right.addStretch(); body.addLayout(right,1)
    def _general(self):
        workflow=tr(WORKFLOW_LABELS[blast_workflow_for(self.controller.state,self.blast_event)])
        page=QWidget(); layout=QVBoxLayout(page); top=QHBoxLayout(); info=CardFrame("General information"); grid=QGridLayout(); info.layout.addLayout(grid); values=(("Name",self.blast_event.name),("ID",self.blast_event.id),("Type","Contour"),("Domain",self.domain_name),("Horizon",f"{self.blast_event.elevation:g} m"),("Planned blast date",self.blast_event.event_date or "—"),("Status",workflow),("Archive",tr("Archived") if self.blast_event.is_archived else "—"),("Active geometry revision",self.rev.revision_number if self.rev else "—"),("Source geometry file",self.rev.source_file_name if self.rev else "—"),("Geometry import date",self.rev.imported_at.date() if self.rev else "—")); self.general_information={}
        for row,(name,value) in enumerate(values):left=QLabel(tr(name)); left.setObjectName("MutedText"); right=QLabel(str(value)); self.general_information[name]=right; grid.addWidget(left,row,0); grid.addWidget(right,row,1)
        top.addWidget(info,3); dataset=self.controller.state.active_dataset(); self.plan=PlanGeometryWidget(); self.plan.set_geometry(self.rev.plan_geometry if self.rev else None,dataset.lines if dataset else [],f"{tr('Horizon')}: {self.blast_event.elevation:g} | {tr('Source')}: {self.rev.source_file_name if self.rev else '—'}"); self.plan.set_reimport_enabled(not self.read_only); self.plan.reimport_requested.connect(self.reimport_geometry); top.addWidget(self.plan,2); layout.addLayout(top)
        contour=self.draft.contour_parameters; actual=self.draft.actual_execution; cards=QHBoxLayout(); design=CardFrame("Blast design parameters"); execution=CardFrame("Execution fact"); design_text=QLabel(); execution_text=QLabel(); design_text.setWordWrap(True); execution_text.setWordWrap(True)
        if contour:design_text.setText(f"{tr('Controlled blasting method')}: {_show(contour.controlled_blasting_method)}\n{tr('Line length')}: {_show(contour.line_length_m,' m')}\n{tr('Hole count')}: {_show(contour.hole_count)}\n{tr('Average spacing')}: {_show(contour.average_spacing_m,' m')}\n{tr('Average depth')}: {_show(contour.average_depth_m,' m')}\n{tr('Diameter')}: {_show(contour.diameter_mm,' mm')}\n{tr('Explosive type')}: {_show(contour.explosive_type)}")
        else:design_text.setText(tr("No design data"))
        execution_text.setText(f"{tr('Completion status')}: {_show(actual.completion_status)}\n{tr('Actual blast date')}: {_show(actual.actual_blast_date)}\n{tr('Actual hole count')}: {_show(actual.actual_total_hole_count)}\n{tr('Actual drilling length')}: {_show(actual.actual_total_drilling_length_m,' m')}\n{tr('Actual explosive mass')}: {_show(actual.actual_total_explosive_mass_kg,' kg')}"); design.layout.addWidget(design_text); execution.layout.addWidget(execution_text); cards.addWidget(design); cards.addWidget(execution); layout.addLayout(cards)
        bottom=QHBoxLayout(); comments=CardFrame("Comments"); comment=QLabel((self.draft.notes+"\n"+actual.execution_notes).strip() or tr("No comments")); comment.setWordWrap(True); comments.layout.addWidget(comment); recent=CardFrame("Recent history"); geometry_lines=[f"{tr('Geometry')} R{x.revision_number}: {x.imported_at.date()}" for x in self.blast_event.geometry_revisions[-3:]]; card_lines=[f"{tr('Technical Card')} R{x.revision_number}: {x.status}, {x.created_at.date()}" for x in self.card.revisions[-3:]]; history=QLabel("\n".join(geometry_lines+card_lines) or tr("No history")); history.setWordWrap(True); recent.layout.addWidget(history); bottom.addWidget(comments,3); bottom.addWidget(recent,2); layout.addLayout(bottom); layout.addWidget(self.editor.take_tab(tr("General"))); self.tabs.addTab(page,tr("General information"))
    def _attachments(self,title):
        kind="photo" if title=="Photos" else "document"; page,manager=create_attachment_tab_page(self.controller.attachments,"blast_event",self.blast_event.id,kind,read_only=self.read_only); manager.changed.connect(self._after_attachment_change); return page
    def _after_attachment_change(self):
        self._refresh_sidebar(); self._refresh_history()
    def _refresh_history(self):
        self.history.set_entries(self.history_repo.for_blast_event(self.blast_event.id))
    def _refresh_sidebar(self):
        photos=self.controller.attachments.list_for_owner("blast_event",self.blast_event.id,"photo"); documents=self.controller.attachments.list_for_owner("blast_event",self.blast_event.id,"document"); active=self.card.active_revision(); rows=(("Status",tr(WORKFLOW_LABELS[blast_workflow_for(self.controller.state,self.blast_event)])),("Archive",tr("Archived") if self.blast_event.is_archived else "—"),("Planned blast date",self.blast_event.event_date or "—"),("Horizon",f"{self.blast_event.elevation:g} m"),("Geometry revision",self.rev.revision_number if self.rev else "—"),("Technical Card revision",active.revision_number if active else "—"),("Technical Card status",active.status if active else self.draft.status),("Photos",len(photos)),("Documents",len(documents)),("History records",len(self.history_repo.for_blast_event(self.blast_event.id))))
        while self.summary_grid.count():
            item=self.summary_grid.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for row,(name,value) in enumerate(rows):self.summary_grid.addWidget(QLabel(tr(name)),row,0); self.summary_grid.addWidget(QLabel(str(value)),row,1)
        self.photo_preview.set_items(photos,tr("No photos yet")); self.document_preview.set_items(documents,tr("No documents yet")); self.photo_preview.add_button.setEnabled(True); self.document_preview.add_button.setEnabled(True)
    def reimport_geometry(self):
        if self.read_only:QMessageBox.warning(self,tr("Read only"),tr("Archived contour events and Viewer accounts are read-only.")); return
        path,_=QFileDialog.getOpenFileName(self,tr("Reimport contour geometry"),"",tr("Geometry files (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"))
        if not path:return
        try:self.controller.reimport_blast_event_geometry(self.blast_event,path)
        except Exception as exc:QMessageBox.warning(self,tr("Contour geometry"),domain_message(str(exc)))
        self._refresh_history()
    def save_draft(self):
        if self.read_only:QMessageBox.warning(self,tr("Read only"),tr("This contour event is read-only.")); return False
        saved=self.editor.save_draft()
        if saved:self._refresh_workflow_presentation(); self._refresh_sidebar(); self._refresh_history()
        return saved
    def complete(self):
        if self.read_only:QMessageBox.warning(self,tr("Read only"),tr("This contour event is read-only.")); return False
        saved=self.editor.complete()
        if saved:self._refresh_workflow_presentation(); self._refresh_sidebar(); self._refresh_history()
        return saved