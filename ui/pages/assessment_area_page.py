from app.localization import tr
from domain.blasting.workflow import ASSESSMENT_PROGRESS_LABELS, assessment_progress_for
"""Normal, revision-safe page for one Assessment Area."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout,QFrame,QGridLayout,QHBoxLayout,QInputDialog,QLabel,QListWidget,QListWidgetItem,QMessageBox,QPushButton,
                               QSizePolicy,QSplitter,QTabWidget,QVBoxLayout,QWidget)
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.pages.block_card_widgets import AttachmentPreviewWidget,CardFrame,apply_workflow_badge_style
from ui.editors.assessment_evaluation_editor import AssessmentAreaEvaluationDialog
from ui.presentation_labels import format_assessment_elevation_interval, result_label


def _value(value): return "—" if value in (None,"") else str(value)

class AssessmentLinkListItem(QFrame):
    STATUS_COLORS={"suggested":("#fff8e6","#d6a632"),"confirmed":("#edf8f0","#58a66a"),"excluded":("#f3f4f6","#9ca3af")}
    def __init__(self,event,link,stale,parent=None):
        super().__init__(parent); self.workflow_status=link.status; self.is_stale=stale; self.setObjectName("AssessmentLinkItem")
        layout=QVBoxLayout(self); layout.setContentsMargins(9,7,9,7); layout.setSpacing(3)
        title=QLabel(event.name); title.setStyleSheet("font-weight:600"); layout.addWidget(title); detail=QLabel(f"{tr(event.event_type.title())} · {event.elevation:g} m"); detail.setObjectName("MutedText"); layout.addWidget(detail)
        badges=QHBoxLayout(); status=QLabel(tr(link.status.title())); status.setObjectName("LinkStatusBadge"); badges.addWidget(status)
        if stale:
            stale_badge=QLabel(tr("Stale")); stale_badge.setObjectName("StaleBadge"); badges.addWidget(stale_badge)
        badges.addStretch(); source=QLabel(f"{tr(link.source.title())} · {link.geometry_revision_id}"); source.setObjectName("MutedText"); badges.addWidget(source); layout.addLayout(badges)
        self.set_selected(False)
    def set_selected(self,selected):
        background,accent=self.STATUS_COLORS[self.workflow_status]; border="#2563a6" if selected else accent; width=2 if selected else 1
        self.setStyleSheet(f"QFrame#AssessmentLinkItem{{background:{background};border:{width}px solid {border};border-radius:5px}} QLabel#LinkStatusBadge{{font-weight:600;color:#374151}} QLabel#StaleBadge{{background:#fff1c2;color:#8a5a00;border:1px solid #e5b94d;border-radius:4px;padding:1px 4px}}")

class AssessmentAreaPage(QWidget):
    edit_boundaries_requested=Signal(str)
    metadata_saved=Signal(str,int)
    def __init__(self,context,domain_id,domain_name,area_id,parent=None):
        super().__init__(parent); self.context=context; self.domain_id=domain_id; self.domain_name=domain_name; self.area_id=area_id; self.controller=EntityPageController(context,domain_id); self.area=self.controller.area(area_id); self.read_only=not context.current_user.can_edit or self.area.is_archived
        self._build_editor()
        root=QVBoxLayout(self); self._header(root); body=QHBoxLayout(); left=QVBoxLayout(); self.tabs=QTabWidget(); left.addWidget(self.tabs); body.addLayout(left,4); self._sidebar(body); root.addLayout(body)
        self._overview(); self.tabs.addTab(self.assessment_tab,tr("Assessment")); self._linked_events(); self._attachment_tab("Photos"); self._attachment_tab("Documents"); self.tabs.addTab(self.history,tr("History")); self._refresh_overview_and_sidebar()
        self.setStyleSheet("#CardFrame,#CriterionCard,#ResultCard{background:white;border:1px solid #dfe3ea;border-radius:6px} #CardTitle{font-weight:600;color:#111827} #EntityTitle{font-size:24px;font-weight:700} #StatusBadge{background:#fff4d6;color:#8a5a00;border:1px solid #f4c76b;border-radius:5px;padding:4px 8px} #MetaBadge{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:5px;padding:4px 8px} #MutedText{color:#6b7280}")

    def _header(self,root):
        card=CardFrame(); top=QHBoxLayout(); title=QLabel(self.area.name); title.setObjectName("EntityTitle"); self.header_status=QLabel(); apply_workflow_badge_style(self.header_status); top.addWidget(title); top.addWidget(self.header_status)
        if self.area.is_archived: top.addWidget(QLabel(tr("Archived")))
        top.addStretch(); self.edit_button=QPushButton(tr("Edit")); self.edit_button.setEnabled(not self.read_only); self.edit_button.clicked.connect(self.edit_metadata); top.addWidget(self.edit_button); card.layout.addLayout(top); rev=self.area.active_geometry_revision(); meta=QHBoxLayout()
        interval=format_assessment_elevation_interval(rev.min_elevation,rev.max_elevation)
        for text in (f"{tr('ID')}: {self.area.id}",f"{tr('Domain')}: {self.domain_name}",f"{tr('Assessment date')}: {self.area.assessment_date}",f"{tr('Elevation interval')}: {interval}",f"{tr('Revision')}: {rev.revision_number}"):
            badge=QLabel(text); badge.setObjectName("MetaBadge"); meta.addWidget(badge)
        meta.addStretch(); card.layout.addLayout(meta); root.addWidget(card)

    def edit_metadata(self):
        from repositories.domain_repository import DomainRepository
        from ui.dialogs.entity_metadata_dialogs import AssessmentAreaMetadataDialog
        repo=DomainRepository(self.context.session_factory); domains=repo.selectable_for_site(self.controller.site_id)
        dialog=AssessmentAreaMetadataDialog(domains,self.controller.domain_id,self.area.name,self)
        if not dialog.exec():return
        name=dialog.name.text().strip(); target_id,target_version=dialog.selected_domain
        if not name:QMessageBox.warning(self,tr("Could not save"),tr("Name is required"));return
        try:self.controller.update_assessment_area_metadata(self.area,name=name,target_domain_id=target_id,target_expected_version=target_version)
        except Exception as exc:QMessageBox.warning(self,tr("Could not save"),str(exc));return
        self.metadata_saved.emit(self.area.id,target_id)

    def _build_editor(self):
        evaluation,draft=self.controller.evaluation_draft(self.area); self.evaluation=evaluation
        self.evaluation_editor=AssessmentAreaEvaluationDialog(self.area,evaluation,draft,self.controller.save_evaluation,None,read_only=self.read_only)
        obsolete=[self.evaluation_editor.take_tab(tr(title)) for title in ("General","Geometry","Face condition")]
        self.assessment_tab=QWidget(); layout=QVBoxLayout(self.assessment_tab); layout.setContentsMargins(4,4,4,4)
        self.assessment_splitter=QSplitter(Qt.Orientation.Horizontal); self.assessment_splitter.setChildrenCollapsible(False)
        self.assessment_inputs=QWidget(); self.assessment_inputs.setMinimumWidth(500); inputs=QVBoxLayout(self.assessment_inputs); inputs.setContentsMargins(4,2,4,2); inputs.setSpacing(7)
        if not self.read_only and not self.evaluation_editor.inspector.text().strip(): self.evaluation_editor.inspector.setText(getattr(self.context.current_user,"display_name","") or "")
        self.assessment_details_card=QFrame(); self.assessment_details_card.setObjectName("CriterionCard"); details=QVBoxLayout(self.assessment_details_card); details.setContentsMargins(8,5,8,5); details.addWidget(QLabel(f"<b>{tr('Assessment details')}</b>")); metadata=QHBoxLayout(); metadata.addWidget(QLabel(tr("Assessment date"))); metadata.addWidget(self.evaluation_editor.date); metadata.addSpacing(12); metadata.addWidget(QLabel(tr("Inspector"))); metadata.addWidget(self.evaluation_editor.inspector,1); details.addLayout(metadata); inputs.addWidget(self.assessment_details_card)
        inputs.addSpacing(14); self.geometry_section_title=QLabel(f"<b>{tr('Geometry')}</b>"); inputs.addWidget(self.geometry_section_title)
        geometry_line=QFrame(); geometry_line.setFixedHeight(1); geometry_line.setStyleSheet("background:#dfe3ea;border:0"); geometry_line.setObjectName("SectionDivider"); inputs.addWidget(geometry_line)
        for editor in self.evaluation_editor.geometry_editors.values():inputs.addWidget(editor)
        inputs.addSpacing(14); self.face_condition_section_title=QLabel(f"<b>{tr('Face condition')}</b>"); inputs.addWidget(self.face_condition_section_title)
        self.face_condition_divider=QFrame(); self.face_condition_divider.setFixedHeight(1); self.face_condition_divider.setStyleSheet("background:#dfe3ea;border:0"); self.face_condition_divider.setObjectName("SectionDivider"); inputs.addWidget(self.face_condition_divider)
        for editor in self.evaluation_editor.editors.values():inputs.addWidget(editor)
        inputs.setAlignment(Qt.AlignmentFlag.AlignTop); self.assessment_splitter.addWidget(self.assessment_inputs)
        self.assessment_right=QWidget(); self.assessment_right.setMinimumWidth(360); self.assessment_right.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding); right=QVBoxLayout(self.assessment_right); right.setContentsMargins(0,0,0,0); right.setSpacing(7)
        matrix_context_card=QFrame(); matrix_context_card.setObjectName("CriterionCard"); basis=QVBoxLayout(matrix_context_card); basis.setContentsMargins(10,6,10,6); basis.addWidget(QLabel(f"<b>{tr('Assessment basis')}</b>")); controlled=draft.matrix_template_id=="controlled_blasting_v1"; self.assessment_basis_value=QLabel(tr("Controlled blasting") if controlled else tr("Standard blasting")); self.assessment_basis_value.setObjectName("MetaBadge"); basis.addWidget(self.assessment_basis_value,0,Qt.AlignmentFlag.AlignLeft); source=draft.controlled_blasting_detection_source; detection={"confirmed_link":tr("Confirmed contour blast link"),"no_confirmed_contour_link":tr("No confirmed contour blast link"),"manual_override":tr("Manual matrix selection")}.get(source,source); self.assessment_basis_detection=QLabel(detection); self.assessment_basis_detection.setObjectName("MutedText"); basis.addWidget(self.assessment_basis_detection)
        self.override_reason_label=QLabel(tr("Manual matrix selection reason")); basis.addWidget(self.override_reason_label); basis.addWidget(self.evaluation_editor.override_reason); manual_matrix=source=="manual_override"; self.override_reason_label.setVisible(manual_matrix); self.evaluation_editor.override_reason.setVisible(manual_matrix)
        right.addWidget(matrix_context_card); self.result=self.evaluation_editor.take_tab(tr("Matrix"),self.assessment_right); self.result.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding); right.addWidget(self.result,1); self.result.show(); self.assessment_splitter.addWidget(self.assessment_right)
        self.assessment_splitter.setStretchFactor(0,55); self.assessment_splitter.setStretchFactor(1,45); self.assessment_splitter.setSizes([550,450]); layout.addWidget(self.assessment_splitter,1)
        self.evaluation_editor.comments.setMaximumHeight(65); self.evaluation_editor.recommendations.setMaximumHeight(65); notes=QFormLayout(); notes.setVerticalSpacing(3); self.comments_label=QLabel(tr("Comments")); self.recommendations_label=QLabel(tr("Recommendations")); notes.addRow(self.comments_label,self.evaluation_editor.comments); notes.addRow(self.recommendations_label,self.evaluation_editor.recommendations); layout.addLayout(notes)
        controls=QHBoxLayout(); controls.addStretch(); self.save_evaluation_button=QPushButton(tr("Save draft")); self.complete_evaluation_button=QPushButton(tr("Complete assessment"));
        for button in (self.save_evaluation_button,self.complete_evaluation_button):button.setEnabled(not self.read_only); controls.addWidget(button)
        self.save_evaluation_button.clicked.connect(lambda:self._save_evaluation("draft")); self.complete_evaluation_button.clicked.connect(lambda:self._save_evaluation("completed")); layout.addLayout(controls)
        for page in obsolete:page.deleteLater()
        self.history=self.evaluation_editor.take_tab(tr("History"))

    def _sidebar(self,body):
        right=QVBoxLayout(); self.summary_card=CardFrame("Summary"); self.summary_grid=QGridLayout(); self.summary_card.layout.addLayout(self.summary_grid); right.addWidget(self.summary_card)
        self.photo_preview=AttachmentPreviewWidget("Photos"); self.document_preview=AttachmentPreviewWidget("Documents"); self.photo_preview.add_button.clicked.connect(lambda:self.tabs.setCurrentWidget(self.photos_tab)); self.document_preview.add_button.clicked.connect(lambda:self.tabs.setCurrentWidget(self.documents_tab)); right.addWidget(self.photo_preview); right.addWidget(self.document_preview); right.addStretch(); body.addLayout(right,1)

    def _overview(self):
        page=QWidget(); layout=QVBoxLayout(page); rev=self.area.active_geometry_revision(); top=QHBoxLayout(); self.info_card=CardFrame("General information"); self.info_grid=QGridLayout(); self.info_card.layout.addLayout(self.info_grid); top.addWidget(self.info_card,3)
        interval=format_assessment_elevation_interval(rev.min_elevation,rev.max_elevation); self.plan=PlanGeometryWidget(); dataset=next((d for d in self.controller.state.datasets if d.id==(rev.source_dataset_ids[0] if rev.source_dataset_ids else None)),None); self.plan.use_center_control(); self.plan.set_geometry(rev.final_geometry_frozen,dataset.lines if dataset else [],f"{tr('Elevation interval')}: {interval}",focus_geometry=rev.final_geometry_frozen); top.addWidget(self.plan,2); layout.addLayout(top)
        cards=QHBoxLayout(); self.result_card,self.links_card,self.geometry_card=(CardFrame(x) for x in ("Assessment result","Linked events","Geometry")); self.result_text=QLabel(); self.links_text=QLabel(); self.geometry_text=QLabel();
        for card,label in ((self.result_card,self.result_text),(self.links_card,self.links_text),(self.geometry_card,self.geometry_text)):label.setWordWrap(True); card.layout.addWidget(label); cards.addWidget(card)
        layout.addLayout(cards); bottom=QHBoxLayout(); self.comments_card=CardFrame("Comments / recommendations"); self.comments_text=QLabel(); self.comments_text.setWordWrap(True); self.comments_card.layout.addWidget(self.comments_text); self.recent_card=CardFrame("Recent history"); self.recent_text=QLabel(); self.recent_text.setWordWrap(True); self.recent_card.layout.addWidget(self.recent_text); bottom.addWidget(self.comments_card,3); bottom.addWidget(self.recent_card,2); layout.addLayout(bottom)
        self.edit_boundaries_button=QPushButton(tr("Edit boundaries")); self.edit_boundaries_button.setEnabled(not self.read_only); self.edit_boundaries_button.clicked.connect(self._request_edit_boundaries); layout.addWidget(self.edit_boundaries_button); self.tabs.addTab(page,tr("Overview"))

    def _refresh_overview_and_sidebar(self):
        rev=self.area.active_geometry_revision(); active=self.evaluation.active_revision(); confirmed=[x for x in self.area.links_for_revision() if x.status=="confirmed"]; prod=sum(self.controller.links.event(x.blast_event_id).event_type=="production" for x in confirmed); contour=len(confirmed)-prod; status=tr(ASSESSMENT_PROGRESS_LABELS[assessment_progress_for(self.area,self.evaluation)]); self.header_status.setText(status + ((" · " + tr("Archived")) if self.area.is_archived else ""))
        while self.info_grid.count():
            item=self.info_grid.takeAt(0)
            if item.widget():item.widget().deleteLater()
        interval=format_assessment_elevation_interval(rev.min_elevation,rev.max_elevation); rows=(("Name",self.area.name),("ID",self.area.id),("Domain",self.domain_name),("Assessment date",self.area.assessment_date),("Status",status),("Archive",tr("Archived") if self.area.is_archived else "—"),("Elevation interval",interval),("Active geometry revision",rev.revision_number),("Project Lines Dataset",', '.join(rev.source_dataset_ids) or 'Free boundary'))
        self.general_information={}
        for row,(name,value) in enumerate(rows):left=QLabel(tr(name)); left.setObjectName("MutedText"); right=QLabel(_value(value)); self.general_information[name]=right; self.info_grid.addWidget(left,row,0); self.info_grid.addWidget(right,row,1)
        evaluation_status=active.status if active else "—"; dai=f"{active.design_achievement_index:.3f}" if active and active.design_achievement_index is not None else "—"; fci=f"{active.face_condition_index:.3f}" if active and active.face_condition_index is not None else "—"; quadrant=result_label(active.result_label) if active else "—"
        self.result_text.setText(f"{tr('Evaluation status')}: {evaluation_status}\nDAI: {dai}\nFCI: {fci}\n{tr('Result')}: {_value(quadrant)}"); self.links_text.setText(f"{tr('Production blasts')}: {prod}\n{tr('Contour blasts')}: {contour}\n{tr('Total confirmed')}: {len(confirmed)}"); self.geometry_text.setText(f"{tr('Elevation interval')}: {interval}\n{tr('Revision')}: {rev.revision_number}\n{tr('Project Lines Dataset')}: {', '.join(rev.source_dataset_ids) or 'Free boundary'}")
        comments=((active.comments or "")+("\n" if active and active.comments and active.recommendations else "")+(active.recommendations or "")) if active else ""; self.comments_text.setText(comments or tr("No comments or recommendations")); geometry_history="\n".join(f"{tr('Geometry')} R{x.revision_number}: {x.created_at.date()}" for x in self.area.geometry_revisions[-3:]); evaluation_history="\n".join(f"{tr('Assessment')} R{x.revision_number}: {x.status}, {x.created_at.date()}" for x in self.evaluation.revisions[-3:]); self.recent_text.setText((geometry_history+"\n"+evaluation_history).strip())
        while self.summary_grid.count():
            item=self.summary_grid.takeAt(0)
            if item.widget():item.widget().deleteLater()
        summary=(("Status",status),("Assessment date",self.area.assessment_date),("Evaluation status",evaluation_status),("DAI",dai),("FCI",fci),("Linked events",len(confirmed)),("Geometry revisions",len(self.area.geometry_revisions)),("Evaluation revisions",len(self.evaluation.revisions)))
        for row,(name,value) in enumerate(summary):self.summary_grid.addWidget(QLabel(tr(name)),row,0); self.summary_grid.addWidget(QLabel(_value(value)),row,1)
        persisted=self.evaluation in self.controller.state.evaluations; photos=self.controller.attachments.list_for_owner("assessment_evaluation",self.evaluation.id,"photo") if persisted else []; documents=self.controller.attachments.list_for_owner("assessment_evaluation",self.evaluation.id,"document") if persisted else []; self.photo_preview.set_items(photos,tr("No photos yet")); self.document_preview.set_items(documents,tr("No documents yet")); self.photo_preview.add_button.setEnabled(True); self.document_preview.add_button.setEnabled(True)

    def _linked_events(self):
        page=QWidget(); layout=QVBoxLayout(page); self.links_splitter=QSplitter(Qt.Orientation.Horizontal); self.links_splitter.setChildrenCollapsible(False)
        left=QWidget(); left.setMinimumWidth(300); left.setMaximumWidth(380); left_layout=QVBoxLayout(left); left_layout.setContentsMargins(0,0,4,0); left_layout.setSpacing(6)
        self.links_list=QListWidget(); self.links_list.setSpacing(5); self.links_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection); left_layout.addWidget(self.links_list,1)
        selected_actions=QHBoxLayout(); global_actions=QHBoxLayout()
        self.link_action_buttons={}
        for label,callback in (("Confirm",self.confirm_link),("Exclude",self.exclude_link),("Restore suggestion",self.restore_link)):
            button=QPushButton(tr(label)); button.setEnabled(not self.read_only); button.clicked.connect(callback); selected_actions.addWidget(button); self.link_action_buttons[label]=button
        for label,callback in (("Add manually",self.add_manual_link),("Recalculate links",self.recalculate_links)):
            button=QPushButton(tr(label)); button.setEnabled(not self.read_only); button.clicked.connect(callback); global_actions.addWidget(button); self.link_action_buttons[label]=button
        left_layout.addLayout(selected_actions); left_layout.addLayout(global_actions); self.links_splitter.addWidget(left)
        detail=QFrame(); detail.setObjectName("CriterionCard"); detail_layout=QVBoxLayout(detail); detail_layout.setContentsMargins(8,6,8,8); detail_layout.setSpacing(5)
        header=QHBoxLayout(); names=QVBoxLayout(); self.link_event_name=QLabel(tr("Select a linked event")); self.link_event_name.setObjectName("CardTitle"); self.link_event_detail=QLabel(); self.link_event_detail.setObjectName("MutedText"); names.addWidget(self.link_event_name); names.addWidget(self.link_event_detail); header.addLayout(names,1); self.link_event_type=QLabel(); self.link_event_type.setObjectName("MetaBadge"); header.addWidget(self.link_event_type); detail_layout.addLayout(header)
        self.link_status_line=QLabel(); self.link_status_line.setTextFormat(Qt.TextFormat.RichText); detail_layout.addWidget(self.link_status_line)
        self.link_warning=QLabel(); self.link_warning.setWordWrap(True); self.link_warning.setStyleSheet("background:#fff8e6;color:#8a5a00;border:1px solid #e5b94d;border-radius:4px;padding:5px"); self.link_warning.hide(); detail_layout.addWidget(self.link_warning)
        legend=QLabel(f"<span style='color:#1261a0'>■</span> {tr('Assessment area')} &nbsp;&nbsp; <span style='color:#d97706'>■</span> {tr('Blast event')} &nbsp;&nbsp; <span style='color:#9ca3af'>━</span> {tr('Project Lines')}"); detail_layout.addWidget(legend)
        self.link_preview=PlanGeometryWidget(); self.link_preview.reimport_button.hide(); self.link_preview.set_context_visible(False); self.link_preview.use_center_control(); detail_layout.addWidget(self.link_preview,1); self.links_splitter.addWidget(detail)
        self.links_splitter.setStretchFactor(0,0); self.links_splitter.setStretchFactor(1,1); self.links_splitter.setSizes([340,760]); layout.addWidget(self.links_splitter)
        self.links_list.currentRowChanged.connect(self._link_selection_changed); self.tabs.addTab(page,tr("Linked events")); self._link_preview_initialized=False; self.refresh_links()
    def refresh_links(self):
        selected=self._selected_link(); selected_id=selected.id if selected else None; links=self.area.links_for_revision(); self.links_list.clear(); self._link_item_widgets=[]
        for link in links:
            event=self.controller.links.event(link.blast_event_id); widget=AssessmentLinkListItem(event,link,self.controller.links.is_stale(link)); item=QListWidgetItem(); item.setSizeHint(widget.sizeHint()); item.setData(Qt.ItemDataRole.UserRole,link.id); self.links_list.addItem(item); self.links_list.setItemWidget(item,widget); self._link_item_widgets.append(widget)
        row=next((index for index,item in enumerate(links) if item.id==selected_id),0 if links else -1)
        if row>=0:self.links_list.setCurrentRow(row)
        else:self.refresh_link_preview()
    def _link_selection_changed(self,_row):
        for row,widget in enumerate(self._link_item_widgets):widget.set_selected(row==self.links_list.currentRow())
        self.refresh_link_preview()
    def _selected_link(self):
        row=self.links_list.currentRow() if hasattr(self,"links_list") else -1; links=self.area.links_for_revision(); return links[row] if 0<=row<len(links) else None
    def _change_link(self,method):
        if not self._ensure_editable():return
        link=self._selected_link()
        if link:method(self.area,link.id); self.refresh_links(); self._refresh_overview_and_sidebar()
    def confirm_link(self):self._change_link(self.controller.confirm_event_link)
    def exclude_link(self):self._change_link(self.controller.exclude_event_link)
    def restore_link(self):self._change_link(self.controller.restore_event_link)
    def recalculate_links(self):
        if self._ensure_editable():self.controller.refresh_event_link_suggestions(self.area); self.refresh_links(); self._refresh_overview_and_sidebar()
    def add_manual_link(self):
        if not self._ensure_editable():return
        events=[e for e in self.controller.state.blast_events if not e.is_archived]; labels=[f"{e.name} ({e.event_type}, {e.elevation:g})" for e in events]; selected,ok=QInputDialog.getItem(self,tr("Add linked event"),tr("BlastEvent"),labels,0,False)
        if ok and selected:self.controller.add_manual_event_link(self.area,events[labels.index(selected)].id); self.refresh_links(); self._refresh_overview_and_sidebar()
    def refresh_link_preview(self):
        area_revision=self.area.active_geometry_revision(); dataset=next((d for d in self.controller.state.datasets if d.id==(area_revision.source_dataset_ids[0] if area_revision.source_dataset_ids else None)),None); project_lines=dataset.lines if dataset else []; link=self._selected_link()
        if not link:
            self.link_event_name.setText(tr("Select a linked event")); self.link_event_detail.clear(); self.link_event_type.clear(); self.link_status_line.clear(); self.link_warning.hide(); self.link_preview.set_comparison_geometry(area_revision.final_geometry_frozen,None,project_lines,focus_geometry=area_revision.final_geometry_frozen,recenter=not self._link_preview_initialized); self._link_preview_initialized=True; return
        event=self.controller.links.event(link.blast_event_id); revision=self.controller.links.linked_revision(event,link); stale=self.controller.links.is_stale(link); candidate=self.controller.links.evaluate_event(self.area,event)
        self.link_event_name.setText(event.name); self.link_event_type.setText(tr(event.event_type.title())); self.link_event_detail.setText(f"{event.elevation:g} m · {tr('Revision')} {link.geometry_revision_id}")
        badges=[tr(link.status.title()),tr("Stale") if stale else tr("Current")]
        if candidate.spatial_matches:badges.append(tr("Spatial match"))
        self.link_status_line.setText(" &nbsp; ".join(f"<span style='background:#eef2f7;border:1px solid #d5dbe3;border-radius:4px;padding:2px 5px'><b>{value}</b></span>" for value in badges))
        self.link_warning.setText(tr("Referenced geometry revision is unavailable. Current event geometry was not substituted.")); self.link_warning.setVisible(revision is None)
        self.link_preview.set_comparison_geometry(area_revision.final_geometry_frozen,revision.plan_geometry if revision else None,project_lines,focus_geometry=area_revision.final_geometry_frozen,recenter=not self._link_preview_initialized); self._link_preview_initialized=True

    def _attachment_tab(self,title):
        kind="photo" if title=="Photos" else "document"; from ui.dialogs.entity_attachment_dialog import EntityAttachmentManagerWidget
        persisted=self.evaluation in self.controller.state.evaluations; owner_id=self.evaluation.id if persisted else None; page=QWidget(); layout=QVBoxLayout(page)
        def ensure_owner():
            owner,rollback=self.controller.prepare_evaluation_attachment_owner(self.area,self.evaluation); self.evaluation=owner
            return owner,rollback
        manager=EntityAttachmentManagerWidget(self.controller.attachments,"assessment_evaluation",owner_id,kind,page,read_only=self.read_only,ensure_owner=ensure_owner); manager.changed.connect(self._refresh_overview_and_sidebar); layout.addWidget(manager); self.attachment_controls=getattr(self,"attachment_controls",[]); self.attachment_controls.append((kind,manager)); self.tabs.addTab(page,tr(title));
        if kind=="photo":self.photos_tab=page
        else:self.documents_tab=page
    def _save_evaluation(self,status):
        if not self._ensure_editable():return
        if self.evaluation_editor.save(status):self.evaluation_editor.refresh_history(); self._refresh_attachment_controls(); self._refresh_overview_and_sidebar()
    def _refresh_attachment_controls(self):
        persisted=self.evaluation in self.controller.state.evaluations
        for _kind,manager in getattr(self,"attachment_controls",[]):manager.owner_id=self.evaluation.id if persisted else None; manager.refresh()
    def _ensure_editable(self):
        if self.read_only:QMessageBox.warning(self,tr("Read only"),tr("Archived Assessment Areas and Viewer accounts are read-only.")); return False
        return True
    def _request_edit_boundaries(self):
        if self._ensure_editable():self.edit_boundaries_requested.emit(self.area.id)
