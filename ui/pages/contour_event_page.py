from app.localization import tr
"""Focused Block-style page for one contour BlastEvent (never a BlastBlock)."""
from PySide6.QtWidgets import QFileDialog,QGridLayout,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTabWidget,QVBoxLayout,QWidget
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.pages.block_card_widgets import AttachmentPreviewWidget,CardFrame
from ui.pages.technical_card_widgets import ActualExecutionEditorWidget,BlastDesignEditorWidget,TechnicalCardEditorWidget
from ui.presentation_labels import domain_message


def _show(value,unit=""):return "—" if value in (None,"") else f"{value:g}{unit}" if isinstance(value,(int,float)) else str(value)

class ContourEventPage(QWidget):
    def __init__(self,context,domain_id,domain_name,event_id,parent=None):
        super().__init__(parent); self.context=context; self.domain_name=domain_name; self.controller=EntityPageController(context,domain_id); self.blast_event=next(e for e in self.controller.state.blast_events if e.id==event_id and e.event_type=="contour"); self.read_only=not context.current_user.can_edit or self.blast_event.is_archived; self.rev=self.blast_event.active_geometry_revision()
        card,draft=self.controller.technical_card_draft(self.blast_event); self.card,self.draft=card,draft; self.editor=TechnicalCardEditorWidget(self.blast_event,card,draft,self.controller.save_technical_card,self,self.read_only)
        root=QVBoxLayout(self); self._header(root); body=QHBoxLayout(); left=QVBoxLayout(); self.tabs=QTabWidget(); left.addWidget(self.tabs); actions=QHBoxLayout(); actions.addStretch(); self.draft_button=QPushButton(tr("Save draft")); self.complete_button=QPushButton(tr("Complete")); self.draft_button.setEnabled(not self.read_only); self.complete_button.setEnabled(not self.read_only); self.draft_button.clicked.connect(self.save_draft); self.complete_button.clicked.connect(self.complete); actions.addWidget(self.draft_button); actions.addWidget(self.complete_button); left.addLayout(actions); body.addLayout(left,4); self._sidebar(body); root.addLayout(body)
        self._general(); self.tabs.addTab(BlastDesignEditorWidget(self.editor.take_tab(tr("Contour drilling"))),tr("Blast design")); self.tabs.addTab(ActualExecutionEditorWidget(self.editor.take_tab(tr("Execution fact"))),tr("Execution fact")); self.photos_tab=self._attachments("Photos"); self.documents_tab=self._attachments("Documents"); self.tabs.addTab(self.photos_tab,tr("Photos")); self.tabs.addTab(self.documents_tab,tr("Documents")); self.tabs.addTab(self.editor.take_tab(tr("Revision history")),tr("History")); self._refresh_sidebar()
        self.setStyleSheet("#CardFrame{background:white;border:1px solid #dfe3ea;border-radius:8px} #CardTitle{font-weight:600;color:#111827} #EntityTitle{font-size:24px;font-weight:700} #StatusBadge{background:#eef5ff;color:#174f8a;border:1px solid #b8d3ef;border-radius:5px;padding:4px 8px} #MetaBadge{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:5px;padding:4px 8px} #MutedText{color:#6b7280}")
    def _header(self,root):
        card=CardFrame(); top=QHBoxLayout(); title=QLabel(f"{tr('Contour blast')} {self.blast_event.name}"); title.setObjectName("EntityTitle"); status=QLabel(tr("Archived") if self.blast_event.is_archived else tr("Active")); status.setObjectName("StatusBadge"); top.addWidget(title); top.addStretch(); top.addWidget(status); card.layout.addLayout(top); meta=QHBoxLayout()
        for text in (f"{tr('ID')}: {self.blast_event.id}",f"{tr('Horizon')}: {self.blast_event.elevation:g} m",f"{tr('Domain')}: {self.domain_name}",f"{tr('Date')}: {self.blast_event.event_date or '—'}",f"{tr('Revision')}: {self.rev.revision_number if self.rev else '—'}"):
            badge=QLabel(text); badge.setObjectName("MetaBadge"); meta.addWidget(badge)
        meta.addStretch(); card.layout.addLayout(meta); root.addWidget(card)
    def _sidebar(self,body):
        right=QVBoxLayout(); self.summary=CardFrame("Summary"); self.summary_grid=QGridLayout(); self.summary.layout.addLayout(self.summary_grid); right.addWidget(self.summary); self.photo_preview=AttachmentPreviewWidget("Photos"); self.document_preview=AttachmentPreviewWidget("Documents"); self.photo_preview.add_button.clicked.connect(lambda:self.tabs.setCurrentWidget(self.photos_tab)); self.document_preview.add_button.clicked.connect(lambda:self.tabs.setCurrentWidget(self.documents_tab)); right.addWidget(self.photo_preview); right.addWidget(self.document_preview); right.addStretch(); body.addLayout(right,1)
    def _general(self):
        page=QWidget(); layout=QVBoxLayout(page); top=QHBoxLayout(); info=CardFrame("General information"); grid=QGridLayout(); info.layout.addLayout(grid); values=(("Name",self.blast_event.name),("ID",self.blast_event.id),("Type","Contour"),("Domain",self.domain_name),("Horizon",f"{self.blast_event.elevation:g} m"),("Event date",self.blast_event.event_date or "—"),("Status",tr("Archived") if self.blast_event.is_archived else tr("Active")),("Active geometry revision",self.rev.revision_number if self.rev else "—"),("Source geometry file",self.rev.source_file_name if self.rev else "—"),("Geometry import date",self.rev.imported_at.date() if self.rev else "—")); self.general_information={}
        for row,(name,value) in enumerate(values):left=QLabel(tr(name)); left.setObjectName("MutedText"); right=QLabel(str(value)); self.general_information[name]=right; grid.addWidget(left,row,0); grid.addWidget(right,row,1)
        top.addWidget(info,3); dataset=self.controller.state.active_dataset(); self.plan=PlanGeometryWidget(); self.plan.set_geometry(self.rev.plan_geometry if self.rev else None,dataset.lines if dataset else [],f"{tr('Horizon')}: {self.blast_event.elevation:g} | {tr('Source')}: {self.rev.source_file_name if self.rev else '—'}"); self.plan.set_reimport_enabled(not self.read_only); self.plan.reimport_requested.connect(self.reimport_geometry); top.addWidget(self.plan,2); layout.addLayout(top)
        contour=self.draft.contour_parameters; actual=self.draft.actual_execution; cards=QHBoxLayout(); design=CardFrame("Blast design parameters"); execution=CardFrame("Execution fact"); design_text=QLabel(); execution_text=QLabel(); design_text.setWordWrap(True); execution_text.setWordWrap(True)
        if contour:design_text.setText(f"{tr('Controlled blasting method')}: {_show(contour.controlled_blasting_method)}\n{tr('Line length')}: {_show(contour.line_length_m,' m')}\n{tr('Hole count')}: {_show(contour.hole_count)}\n{tr('Average spacing')}: {_show(contour.average_spacing_m,' m')}\n{tr('Average depth')}: {_show(contour.average_depth_m,' m')}\n{tr('Diameter')}: {_show(contour.diameter_mm,' mm')}\n{tr('Explosive type')}: {_show(contour.explosive_type)}")
        else:design_text.setText(tr("No design data"))
        execution_text.setText(f"{tr('Completion status')}: {_show(actual.completion_status)}\n{tr('Actual blast date')}: {_show(actual.actual_blast_date)}\n{tr('Actual hole count')}: {_show(actual.actual_total_hole_count)}\n{tr('Actual drilling length')}: {_show(actual.actual_total_drilling_length_m,' m')}\n{tr('Actual explosive mass')}: {_show(actual.actual_total_explosive_mass_kg,' kg')}"); design.layout.addWidget(design_text); execution.layout.addWidget(execution_text); cards.addWidget(design); cards.addWidget(execution); layout.addLayout(cards)
        bottom=QHBoxLayout(); comments=CardFrame("Comments"); comment=QLabel((self.draft.notes+"\n"+actual.execution_notes).strip() or tr("No comments")); comment.setWordWrap(True); comments.layout.addWidget(comment); recent=CardFrame("Recent history"); geometry_lines=[f"{tr('Geometry')} R{x.revision_number}: {x.imported_at.date()}" for x in self.blast_event.geometry_revisions[-3:]]; card_lines=[f"{tr('Technical Card')} R{x.revision_number}: {x.status}, {x.created_at.date()}" for x in self.card.revisions[-3:]]; history=QLabel("\n".join(geometry_lines+card_lines) or tr("No history")); history.setWordWrap(True); recent.layout.addWidget(history); bottom.addWidget(comments,3); bottom.addWidget(recent,2); layout.addLayout(bottom); layout.addWidget(self.editor.take_tab(tr("General"))); self.tabs.addTab(page,tr("General information"))
    def _attachments(self,title):
        from ui.dialogs.entity_attachment_dialog import EntityAttachmentManagerWidget
        kind="photo" if title=="Photos" else "document"; page=QWidget(); layout=QVBoxLayout(page); manager=EntityAttachmentManagerWidget(self.controller.attachments,"blast_event",self.blast_event.id,kind,page,read_only=self.read_only); manager.changed.connect(self._refresh_sidebar); layout.addWidget(manager); return page
    def _refresh_sidebar(self):
        photos=self.controller.attachments.list_for_owner("blast_event",self.blast_event.id,"photo"); documents=self.controller.attachments.list_for_owner("blast_event",self.blast_event.id,"document"); active=self.card.active_revision(); rows=(("Status",tr("Archived") if self.blast_event.is_archived else tr("Active")),("Date",self.blast_event.event_date or "—"),("Horizon",f"{self.blast_event.elevation:g} m"),("Geometry revision",self.rev.revision_number if self.rev else "—"),("Technical Card revision",active.revision_number if active else "—"),("Technical Card status",active.status if active else self.draft.status),("Photos",len(photos)),("Documents",len(documents)))
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
    def save_draft(self):
        if self.read_only:QMessageBox.warning(self,tr("Read only"),tr("This contour event is read-only.")); return False
        return self.editor.save_draft()
    def complete(self):
        if self.read_only:QMessageBox.warning(self,tr("Read only"),tr("This contour event is read-only.")); return False
        return self.editor.complete()
