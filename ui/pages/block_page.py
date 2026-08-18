from __future__ import annotations

from app.localization import tr
from ui.presentation_labels import domain_message

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.context import AppContext
from repositories.audit_log_repository import AuditLogRepository
from repositories.entity_history_repository import EntityHistoryRepository
from repositories.production_blast_repository import ProductionBlastRepository, ProductionBlastRow
from repositories.domain_repository import DomainRepository
from infrastructure.services.production_blast_service import ProductionBlastService
from ui.block_dialog import BlockDialog
from ui.pages.block_card_widgets import (
    AuditPreviewWidget,
    BlockOverviewWidget,
    BlockSummaryWidget,
    CommentsWidget,
    CompactInfoCards,
    EmptySection,
    format_datetime,
    format_decimal,
)
from ui.pages.entity_history_widget import EntityHistoryWidget
from ui.pages.entity_history_revision_viewer import open_geometry_revision, open_technical_card_revision
from ui.pages.entity_overview_widgets import EntityHeaderWidget, QuickAttachmentPreview
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.entity_tabs import create_attachment_tab_page, create_entity_tabs
from ui.pages.technical_card_widgets import (ActualExecutionEditorWidget,
    BlastDesignEditorWidget, GeomechanicsEditorWidget, TechnicalCardEditorWidget)
from domain.blasting.workflow import WORKFLOW_LABELS, BlastWorkflowState


class _NullAttachmentService:
    def list_for_owner(self,*args):return []

class BlockPage(QWidget):
    data_changed = Signal()
    metadata_saved = Signal(str,int)

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.domain_repo = DomainRepository(context.session_factory)
        self.block_repo = ProductionBlastRepository(context.session_factory)
        self.block_service = ProductionBlastService(self.block_repo, self.domain_repo)
        self.audit_repo = AuditLogRepository(context.session_factory)
        self.history_repo = EntityHistoryRepository(context.session_factory)
        self.filters = {"number_query": None, "domain_id": None, "site_id": None, "status": None}
        self.current_block: ProductionBlastRow | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.header = EntityHeaderWidget("Select a block")
        self.header.edit_button.clicked.connect(self.edit_current_block)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.tabs = create_entity_tabs()
        self.overview_tab = QWidget()
        overview_layout = QVBoxLayout(self.overview_tab)
        self.overview = BlockOverviewWidget()
        self.overview.scheme.use_center_control()
        self.compact_cards = CompactInfoCards()
        bottom = QHBoxLayout()
        self.comments = CommentsWidget()
        self.comments.edit_button.clicked.connect(self.edit_comment)
        self.audit_preview = AuditPreviewWidget()
        bottom.addWidget(self.comments, 3)
        bottom.addWidget(self.audit_preview, 2)
        overview_layout.addWidget(self.overview)
        overview_layout.addWidget(self.compact_cards)
        overview_layout.addLayout(bottom)
        self.tabs.addTab(self.overview_tab, tr("General information"))
        self.geomechanics_tab = EmptySection(); self.design_tab = EmptySection(); self.execution_tab = EmptySection()
        self.tabs.addTab(self.design_tab, tr("Blast design"))
        self.tabs.addTab(self.geomechanics_tab, tr("Geomechanics"))
        self.tabs.addTab(self.execution_tab, tr("Execution fact"))
        self.photos_tab,self.photos_tab_count,self.manage_photos_button=self._make_attachment_tab("photo")
        self.documents_tab,self.documents_tab_count,self.manage_documents_button=self._make_attachment_tab("document")
        self.tabs.addTab(self.photos_tab, tr("Photos"))
        self.tabs.addTab(self.documents_tab, tr("Documents"))
        self.history_tab = EntityHistoryWidget()
        self.history_tab.entryActivated.connect(self._open_history_entry)
        self.tabs.addTab(self.history_tab, tr("History"))
        self.compact_cards.open_buttons[0].clicked.connect(lambda:self.tabs.setCurrentWidget(self.geomechanics_tab))
        self.compact_cards.open_buttons[1].clicked.connect(lambda:self.tabs.setCurrentWidget(self.design_tab))
        self.compact_cards.open_buttons[2].clicked.connect(lambda:self.tabs.setCurrentWidget(self.execution_tab))
        left.addWidget(self.tabs)

        self.engineering_actions_widget = QWidget()
        engineering_actions = QHBoxLayout(self.engineering_actions_widget)
        engineering_actions.setContentsMargins(0,0,0,0)
        engineering_actions.addStretch()
        self.save_engineering_draft = QPushButton(tr("Save draft")); self.complete_engineering = QPushButton(tr("Complete"))
        self.save_engineering_draft.setEnabled(False); self.complete_engineering.setEnabled(False)
        self.save_engineering_draft.clicked.connect(self._save_technical_card_draft); self.complete_engineering.clicked.connect(self._complete_technical_card)
        engineering_actions.addWidget(self.save_engineering_draft); engineering_actions.addWidget(self.complete_engineering)
        left.addWidget(self.engineering_actions_widget)
        self.tabs.currentChanged.connect(self._sync_engineering_actions_visibility)

        body.addLayout(left, 1)

        right = QVBoxLayout()
        self.summary = BlockSummaryWidget()
        self.photos = QuickAttachmentPreview("Photos", "photo")
        self.documents = QuickAttachmentPreview("Documents", "document")
        self.photos.add_requested.connect(lambda:self.photo_manager.add())
        self.documents.add_requested.connect(lambda:self.document_manager.add())
        self.photos.open_page_requested.connect(lambda:self._open_attachments("photo"))
        self.documents.open_page_requested.connect(lambda:self._open_attachments("document"))
        for widget in (self.summary, self.photos, self.documents):
            widget.setMinimumWidth(250)
            widget.setMaximumWidth(290)
        right.addWidget(self.summary)
        right.addWidget(self.photos)
        right.addWidget(self.documents)
        right.addStretch()
        body.addLayout(right, 0)
        layout.addLayout(body)

        self.setStyleSheet(
            """
            #CardFrame { background: #ffffff; border: 1px solid #dfe3ea; border-radius: 8px; }
            #CardTitle { font-weight: 600; color: #111827; }
            #EntityTitle { font-size: 24px; font-weight: 700; }
            #MetaBadge { background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 5px; padding: 4px 8px; }
            #MutedText { color: #6b7280; }
            #SchemePlaceholder { background: #111827; color: #f9fafb; border: 1px solid #334155; border-radius: 6px; font-size: 16px; font-weight: 600; }
            """
        )
        self._sync_engineering_actions_visibility()
        self.refresh()

    def _make_attachment_tab(self,kind):
        page,manager=create_attachment_tab_page(_NullAttachmentService(),"blast_event",None,kind,read_only=True)
        manager.changed.connect(lambda:self._render_current_block())
        if kind=="photo":self.photo_manager=manager
        else:self.document_manager=manager
        return page,QLabel(),manager.mutation_buttons[0]

    def _sync_engineering_actions_visibility(self, *_args):
        self.engineering_actions_widget.setVisible(self.tabs.currentIndex() in (1,2,3))

    def set_filters(self, filters: dict) -> None:
        self.filters = filters
        self.refresh()

    def refresh(self) -> None:
        rows = self.block_service.list_blocks(**self.filters)
        if self.current_block:
            self.current_block = self.block_service.get_block(self.current_block.id)
        if self.current_block is None and rows:
            self.current_block = rows[0]
        self._render_current_block()

    def open_block_id(self, event_id: str) -> None:
        self.current_block = self.block_service.get_block(event_id)
        self._render_current_block()

    def edit_current_block(self) -> None:
        if not self.current_block or not self.context.current_user.can_edit or self.current_block.is_archived:
            return
        dialog = BlockDialog(self.block_service, self.domain_repo, self.context.current_user,
                             block=self.current_block,
                             expected_version=self.entity_controller.expected_version)
        if dialog.exec():
            self.current_block = self.block_service.get_block(dialog.saved_block_id or self.current_block.id)
            self.refresh()
            self.data_changed.emit()
            self.metadata_saved.emit(self.current_block.id,self.current_block.domain_id)

    def edit_comment(self):
        if not self.current_block or not self.context.current_user.can_edit or self.current_block.is_archived:return
        from PySide6.QtWidgets import QInputDialog
        text,ok=QInputDialog.getMultiLineText(self,tr("Comments"),tr("Comment"),self.current_block.comment or "")
        if not ok:return
        try:self.block_service.update_comment(self.current_block.id,text,self.context.current_user,expected_version=self.entity_controller.expected_version)
        except Exception as exc:QMessageBox.warning(self,tr("Could not save block"),domain_message(str(exc)));return
        self.open_block_id(self.current_block.id); self.data_changed.emit()

    def _render_current_block(self) -> None:
        block = self.current_block
        audit_entries = self.audit_repo.list_for_blast_event(block.id) if block else []
        history_entries = self.history_repo.for_blast_event(block.id) if block else []
        self.entity_controller = EntityPageController(self.context, block.domain_id) if block else None
        event = self.entity_controller.production_event(block.id) if self.entity_controller else None
        photos = self.entity_controller.attachments.list_for_owner("blast_event", event.id, "photo") if event else []
        documents = self.entity_controller.attachments.list_for_owner("blast_event", event.id, "document") if event else []
        photo_count, document_count = self.entity_controller.attachments.counts("blast_event", event.id) if event else (0, 0)
        attachments_available = event is not None
        for manager in (self.photo_manager,self.document_manager):
            manager.service=self.entity_controller.attachments if self.entity_controller else _NullAttachmentService(); manager.owner_id=event.id if event else None; manager.read_only=not self.context.current_user.can_edit or bool(block and block.is_archived)
            for button in manager.mutation_buttons:button.setEnabled(attachments_available and not manager.read_only)
            manager.refresh()
        can_add = attachments_available and self.context.current_user.can_edit and not bool(block and block.is_archived)
        self.manage_photos_button.setEnabled(can_add)
        self.manage_documents_button.setEnabled(can_add)
        self.photos_tab_count.setText(f"{photo_count} photo{'s' if photo_count!=1 else ''}" if photo_count else "No photos yet")
        self.documents_tab_count.setText(f"{document_count} document{'s' if document_count!=1 else ''}" if document_count else "No documents yet")
        if block:
            state=BlastWorkflowState(block.status)
            self.header.set_content(
                title=f"{tr('Block')} {block.block_number}",
                status_text=tr(WORKFLOW_LABELS[state]), status_state=state,
                archived=block.is_archived, can_edit=self.context.current_user.can_edit and not block.is_archived,
                meta_values=(
                    f"{tr('ID')}: {block.id}",
                    f"{tr('Horizon')}: {format_decimal(block.horizon_m)}",
                    f"{tr('Project / Quarry')}: {block.site_name}",
                    f"{tr('Domain')}: {block.domain_name}",
                    f"{tr('Created')}: {format_datetime(block.created_at)}",
                    f"{tr('Updated')}: {format_datetime(block.updated_at)}",
                ),
            )
        else:
            self.header.set_content(title=tr("Select a block"),status_text=tr("—"),status_state="unknown")
        self.overview.set_block(block)
        self.compact_cards.set_block(block)
        self.comments.set_block(block)
        self.comments.edit_button.setEnabled(bool(block and self.context.current_user.can_edit and not block.is_archived))
        self.summary.set_data(block, photo_count, document_count, len(history_entries))
        service=self.entity_controller.attachments if self.entity_controller else None
        self.photos.set_items(service,photos,"No photos yet",can_add=can_add)
        self.documents.set_items(service,documents,"No documents yet",can_add=can_add)
        self.audit_preview.set_entries(audit_entries)
        self.history_tab.set_entries(history_entries)
        self._render_engineering(block)
        self._sync_engineering_actions_visibility()

    def _open_history_entry(self, entry):
        if not self.current_block or not self.entity_controller:
            return
        event = self.entity_controller.production_event(self.current_block.id)
        if event is None:
            return
        if entry.source_type == "blast_geometry":
            revision = next((item for item in event.geometry_revisions if item.id == entry.source_id), None)
            if revision is not None:
                dataset = self.entity_controller.state.active_dataset()
                open_geometry_revision(self, revision=revision, project_lines=dataset.lines if dataset else [])
            return
        if entry.source_type == "technical_card":
            card = next((item for item in self.entity_controller.state.technical_cards
                         if item.blast_event_id == event.id), None)
            revision = next((item for item in card.revisions if item.id == entry.source_id), None) if card else None
            if card is not None and revision is not None:
                from app.use_case_factory import create_charge_presets,create_explosive_catalogue
                open_technical_card_revision(
                    self, event=event, card=card, revision=revision,
                    domain_name=self.current_block.domain_name,
                    explosive_products=create_explosive_catalogue(self.context).list_enabled_products(),
                    charge_presets=create_charge_presets(self.context,self.entity_controller.site_id),
                )

    def _open_attachments(self, kind):
        self.tabs.setCurrentWidget(self.photos_tab if kind=="photo" else self.documents_tab)

    def _replace_tab(self, old, new, title):
        index=self.tabs.indexOf(old); self.tabs.removeTab(index); self.tabs.insertTab(index,new,title); return new

    def _render_engineering(self, block):
        self._clear_engineering()
        if block is None:return
        event=self.entity_controller.production_event(block.id)
        if event is None:
            self.overview.scheme.set_geometry(None,context="Production geometry is not loaded")
            return
        editable=self.context.current_user.can_edit and not block.is_archived
        geometry=event.active_geometry_revision(); dataset=self.entity_controller.state.active_dataset(); lines=dataset.lines if dataset else []
        self.overview.scheme.set_geometry(geometry.plan_geometry if geometry else None,lines,
            f"Horizon {event.elevation:g} | {tr('Source')}: {geometry.source_file_name if geometry else '—'} | Revision: {geometry.revision_number if geometry else '—'}",
            focus_geometry=geometry.plan_geometry if geometry else None)
        self._disconnect_reimport()
        self._reimport_callback = lambda: self._reimport_geometry(event)
        self.overview.scheme.reimport_requested.connect(self._reimport_callback)
        card,revision=self.entity_controller.technical_card_draft(event)
        self.compact_cards.set_revision(card.active_revision() or revision)
        from app.use_case_factory import create_charge_presets,create_explosive_catalogue
        editor=TechnicalCardEditorWidget(event,card,revision,self.entity_controller.save_technical_card,
            self,not editable,domain_name=block.domain_name,
            explosive_products=create_explosive_catalogue(self.context).list_enabled_products(),
            charge_presets=create_charge_presets(self.context,self.entity_controller.site_id))
        self.geomechanics_tab=self._replace_tab(self.geomechanics_tab,GeomechanicsEditorWidget(editor.take_tab(tr("Geomechanics"))),"Geomechanics")
        self.design_tab=self._replace_tab(self.design_tab,BlastDesignEditorWidget(editor.take_tab(tr("Drilling and charging"))),"Blast design")
        self.execution_tab=self._replace_tab(self.execution_tab,ActualExecutionEditorWidget(editor.take_tab(tr("Execution fact"))),"Execution fact")
        self.technical_card_editor=editor
        self.save_engineering_draft.setEnabled(not editor.editor.read_only); self.complete_engineering.setEnabled(not editor.editor.read_only)
        self.overview.scheme.set_reimport_enabled(editable)

    def _clear_engineering(self):
        self.compact_cards.set_revision(None)
        for attr,title in (("geomechanics_tab","Geomechanics"),("design_tab","Blast design"),("execution_tab","Execution fact")):
            old=getattr(self,attr); setattr(self,attr,self._replace_tab(old,EmptySection(),title))
        self.save_engineering_draft.setEnabled(False); self.complete_engineering.setEnabled(False); self.technical_card_editor=None
        self.overview.scheme.set_reimport_enabled(False)
        self._disconnect_reimport()

    def _disconnect_reimport(self):
        callback = getattr(self, "_reimport_callback", None)
        if callback is not None:
            self.overview.scheme.reimport_requested.disconnect(callback)
            self._reimport_callback = None

    def _save_technical_card_draft(self):
        if self.technical_card_editor is not None and self.context.current_user.can_edit and self.current_block and not self.current_block.is_archived:
            if self.technical_card_editor.save_draft():
                self._refresh_preserving_active_tab()
    def _complete_technical_card(self):
        if self.technical_card_editor is not None and self.context.current_user.can_edit and self.current_block and not self.current_block.is_archived:
            if self.technical_card_editor.complete():
                self._refresh_preserving_active_tab()

    def _refresh_preserving_active_tab(self):
        title=self.tabs.tabText(self.tabs.currentIndex())
        self.refresh()
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index)==title: self.tabs.setCurrentIndex(index); break

    def _reimport_geometry(self,event):
        if not self.context.current_user.can_edit or self.current_block.is_archived:return
        path,_=QFileDialog.getOpenFileName(self,tr("Reimport production geometry"),"",tr("Geometry files (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"))
        if not path:return
        try:self.entity_controller.reimport_blast_event_geometry(event,path)
        except Exception as exc:QMessageBox.warning(self,tr("Geometry import"),domain_message(str(exc)))
        self._render_current_block()