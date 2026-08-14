from __future__ import annotations

from app.localization import tr
from ui.presentation_labels import domain_message

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from app.context import AppContext
from repositories.audit_log_repository import AuditLogRepository
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.domain_repository import DomainRepository
from infrastructure.services.blast_block_service import BlastBlockService
from ui.block_dialog import BlockDialog
from ui.pages.block_card_widgets import (
    AttachmentPreviewWidget,
    AuditPreviewWidget,
    BlockHeaderWidget,
    BlockOverviewWidget,
    BlockSummaryWidget,
    CommentsWidget,
    CompactInfoCards,
    EmptySection,
)
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.technical_card_widgets import (ActualExecutionEditorWidget,
    BlastDesignEditorWidget, GeomechanicsEditorWidget, TechnicalCardEditorWidget)


class _NullAttachmentService:
    def list_for_owner(self,*args):return []

class BlockPage(QWidget):
    data_changed = Signal()

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.domain_repo = DomainRepository(context.session_factory)
        self.block_repo = BlastBlockRepository(context.session_factory)
        self.block_service = BlastBlockService(self.block_repo, self.domain_repo)
        self.audit_repo = AuditLogRepository(context.session_factory)
        self.filters = {"number_query": None, "domain_id": None, "site_id": None, "status": None}
        self.current_block: BlastBlockRow | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.header = BlockHeaderWidget()
        self.header.edit_button.clicked.connect(self.edit_current_block)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.tabs = QTabWidget()
        self.overview_tab = QWidget()
        overview_layout = QVBoxLayout(self.overview_tab)
        self.overview = BlockOverviewWidget()
        self.compact_cards = CompactInfoCards()
        bottom = QHBoxLayout()
        self.comments = CommentsWidget()
        self.audit_preview = AuditPreviewWidget()
        bottom.addWidget(self.comments, 3)
        bottom.addWidget(self.audit_preview, 2)
        overview_layout.addWidget(self.overview)
        overview_layout.addWidget(self.compact_cards)
        overview_layout.addLayout(bottom)
        self.tabs.addTab(self.overview_tab, tr("General information"))
        self.geomechanics_tab = EmptySection(); self.design_tab = EmptySection(); self.execution_tab = EmptySection()
        self.tabs.addTab(self.geomechanics_tab, tr("Geomechanics"))
        self.tabs.addTab(self.design_tab, tr("Blast design"))
        self.tabs.addTab(self.execution_tab, tr("Execution fact"))
        self.photos_tab,self.photos_tab_count,self.manage_photos_button=self._make_attachment_tab("photo")
        self.documents_tab,self.documents_tab_count,self.manage_documents_button=self._make_attachment_tab("document")
        self.tabs.addTab(self.photos_tab, tr("Photos"))
        self.tabs.addTab(self.documents_tab, tr("Documents"))
        self.history_tab = AuditPreviewWidget("Change history")
        self.tabs.addTab(self.history_tab, tr("History"))
        left.addWidget(self.tabs)
        engineering_actions = QHBoxLayout(); engineering_actions.addStretch()
        self.save_engineering_draft = QPushButton(tr("Save draft")); self.complete_engineering = QPushButton(tr("Complete"))
        self.save_engineering_draft.setEnabled(False); self.complete_engineering.setEnabled(False)
        self.save_engineering_draft.clicked.connect(self._save_technical_card_draft); self.complete_engineering.clicked.connect(self._complete_technical_card)
        engineering_actions.addWidget(self.save_engineering_draft); engineering_actions.addWidget(self.complete_engineering); left.addLayout(engineering_actions)
        body.addLayout(left, 4)

        right = QVBoxLayout()
        self.summary = BlockSummaryWidget()
        self.photos = AttachmentPreviewWidget("Photos")
        self.documents = AttachmentPreviewWidget("Documents")
        self.photos.add_button.clicked.connect(lambda: self._open_attachments("photo"))
        self.documents.add_button.clicked.connect(lambda: self._open_attachments("document"))
        right.addWidget(self.summary)
        right.addWidget(self.photos)
        right.addWidget(self.documents)
        right.addStretch()
        body.addLayout(right, 1)
        layout.addLayout(body)

        self.setStyleSheet(
            """
            #CardFrame { background: #ffffff; border: 1px solid #dfe3ea; border-radius: 8px; }
            #CardTitle { font-weight: 600; color: #111827; }
            #BlockTitle { font-size: 24px; font-weight: 700; }
            #StatusBadge { background: #fff4d6; color: #8a5a00; border: 1px solid #f4c76b; border-radius: 5px; padding: 4px 8px; }
            #MetaBadge { background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 5px; padding: 4px 8px; }
            #MutedText { color: #6b7280; }
            #SchemePlaceholder { background: #111827; color: #f9fafb; border: 1px solid #334155; border-radius: 6px; font-size: 16px; font-weight: 600; }
            QTabWidget::pane { border: 1px solid #dfe3ea; border-radius: 6px; }
            QTabBar::tab:selected { color: #0b63ce; }
            """
        )
        self.refresh()

    def _make_attachment_tab(self,kind):
        from ui.dialogs.entity_attachment_dialog import EntityAttachmentManagerWidget
        page=QWidget(); layout=QVBoxLayout(page); manager=EntityAttachmentManagerWidget(_NullAttachmentService(),"blast_event",None,kind,page,read_only=True); layout.addWidget(manager)
        manager.changed.connect(lambda:self._render_current_block())
        if kind=="photo":self.photo_manager=manager
        else:self.document_manager=manager
        return page,QLabel(),manager.mutation_buttons[0]

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

    def open_block_id(self, block_id: int) -> None:
        self.current_block = self.block_service.get_block(block_id)
        self._render_current_block()

    def create_block(self, domain_id: int | None = None) -> None:
        dialog = BlockDialog(self.block_service, self.domain_repo, self.context.current_user, domain_id=domain_id)
        if dialog.exec():
            self.current_block = self.block_service.get_block(dialog.saved_block_id) if dialog.saved_block_id else None
            self.refresh()
            self.data_changed.emit()

    def edit_current_block(self) -> None:
        if not self.current_block or not self.context.current_user.can_edit:
            return
        dialog = BlockDialog(self.block_service, self.domain_repo, self.context.current_user,
                             block=self.current_block,
                             expected_version=self.entity_controller.expected_version)
        if dialog.exec():
            self.current_block = self.block_service.get_block(dialog.saved_block_id or self.current_block.id)
            self.refresh()
            self.data_changed.emit()

    def _render_current_block(self) -> None:
        block = self.current_block
        audit_entries = self.audit_repo.list_for_block(block.id) if block else []
        self.entity_controller = EntityPageController(self.context, block.domain_id) if block else None
        event = self.entity_controller.event_for_block(block.id) if self.entity_controller else None
        photos = self.entity_controller.attachments.list_for_owner("blast_event", event.id, "photo") if event else []
        documents = self.entity_controller.attachments.list_for_owner("blast_event", event.id, "document") if event else []
        photo_count, document_count = self.entity_controller.attachments.counts("blast_event", event.id) if event else (0, 0)
        attachments_available = event is not None
        for manager in (self.photo_manager,self.document_manager):
            manager.service=self.entity_controller.attachments if self.entity_controller else _NullAttachmentService(); manager.owner_id=event.id if event else None; manager.read_only=not self.context.current_user.can_edit or bool(block and block.is_archived)
            for button in manager.mutation_buttons:button.setEnabled(attachments_available and not manager.read_only)
            manager.refresh()
        self.photos.add_button.setEnabled(attachments_available)
        self.documents.add_button.setEnabled(attachments_available)
        self.manage_photos_button.setEnabled(attachments_available)
        self.manage_documents_button.setEnabled(attachments_available)
        self.photos_tab_count.setText(f"{photo_count} photo{'s' if photo_count!=1 else ''}" if photo_count else "No photos yet")
        self.documents_tab_count.setText(f"{document_count} document{'s' if document_count!=1 else ''}" if document_count else "No documents yet")
        self.header.set_block(block, self.context.current_user.can_edit and not block.is_archived if block else False)
        self.overview.set_block(block)
        self.compact_cards.set_block(block)
        self.comments.set_block(block)
        self.summary.set_data(block, photo_count, document_count, len(audit_entries))
        self.photos.set_items(photos, "No photos yet")
        self.documents.set_items(documents, "No documents yet")
        self.audit_preview.set_entries(audit_entries)
        self.history_tab.set_entries(audit_entries, limit=200)
        self._render_engineering(block)

    def _open_attachments(self, kind):
        self.tabs.setCurrentWidget(self.photos_tab if kind=="photo" else self.documents_tab)

    def _replace_tab(self, old, new, title):
        index=self.tabs.indexOf(old); self.tabs.removeTab(index); self.tabs.insertTab(index,new,title); return new

    def _render_engineering(self, block):
        self._clear_engineering()
        if block is None:return
        event=self.entity_controller.event_for_block(block.id)
        if event is None:
            self.overview.scheme.set_geometry(None,context="Linked production geometry is not loaded")
            return
        editable=self.context.current_user.can_edit and not block.is_archived
        geometry=event.active_geometry_revision(); dataset=self.entity_controller.state.active_dataset(); lines=dataset.lines if dataset else []
        self.overview.scheme.set_geometry(geometry.plan_geometry if geometry else None,lines,
            f"Horizon {event.elevation:g} | {tr('Source')}: {geometry.source_file_name if geometry else '—'} | Revision: {geometry.revision_number if geometry else '—'}")
        self._disconnect_reimport()
        self._reimport_callback = lambda: self._reimport_geometry(event)
        self.overview.scheme.reimport_requested.connect(self._reimport_callback)
        card,revision=self.entity_controller.technical_card_draft(event)
        editor=TechnicalCardEditorWidget(event,card,revision,self.entity_controller.save_technical_card,self,not editable)
        self.geomechanics_tab=self._replace_tab(self.geomechanics_tab,GeomechanicsEditorWidget(editor.take_tab(tr("Geomechanics"))),"Geomechanics")
        self.design_tab=self._replace_tab(self.design_tab,BlastDesignEditorWidget(editor.take_tab(tr("Drilling and charging"))),"Blast design")
        self.execution_tab=self._replace_tab(self.execution_tab,ActualExecutionEditorWidget(editor.take_tab(tr("Execution fact"))),"Execution fact")
        self.technical_card_editor=editor
        self.save_engineering_draft.setEnabled(not editor.editor.read_only); self.complete_engineering.setEnabled(not editor.editor.read_only)
        self.overview.scheme.set_reimport_enabled(editable)

    def _clear_engineering(self):
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
                self.refresh()
    def _complete_technical_card(self):
        if self.technical_card_editor is not None and self.context.current_user.can_edit and self.current_block and not self.current_block.is_archived:
            if self.technical_card_editor.complete():
                self.refresh()

    def _reimport_geometry(self,event):
        if not self.context.current_user.can_edit or not self.current_block or self.current_block.is_archived:
            QMessageBox.warning(self,tr("Read only"),tr("Archived Blocks and Viewer accounts cannot reimport geometry.")); return
        path,_=QFileDialog.getOpenFileName(self,tr("Reimport production geometry"),"",tr("Geometry files (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"))
        if not path:return
        try:
            self.entity_controller.reimport_blast_event_geometry(event,path); self._render_engineering(self.current_block)
        except Exception as exc:QMessageBox.warning(self,tr("Geometry import"),domain_message(str(exc)))
