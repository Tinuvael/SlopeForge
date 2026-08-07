from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from database.app_context import AppContext
from repositories.attachment_repository import AttachmentRepository
from repositories.audit_log_repository import AuditLogRepository
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.domain_repository import DomainRepository
from services.blast_block_service import BlastBlockService
from ui.block_dialog import BlockDialog
from ui.directory_dialog import DirectoryDialog
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


class BlockListPage(QWidget):
    data_changed = Signal()

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.domain_repo = DomainRepository(context.session_factory)
        self.block_repo = BlastBlockRepository(context.session_factory)
        self.block_service = BlastBlockService(self.block_repo, self.domain_repo)
        self.audit_repo = AuditLogRepository(context.session_factory)
        self.attachment_repo = AttachmentRepository(context.session_factory)
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
        self.tabs.addTab(self.overview_tab, "General information")
        self.geomechanics_tab = EmptySection(); self.design_tab = EmptySection(); self.execution_tab = EmptySection()
        self.tabs.addTab(self.geomechanics_tab, "Geomechanics")
        self.tabs.addTab(self.design_tab, "Blast design")
        self.tabs.addTab(self.execution_tab, "Execution fact")
        self.tabs.addTab(EmptySection(), "Documents")
        self.history_tab = AuditPreviewWidget("Change history")
        self.tabs.addTab(self.history_tab, "History")
        left.addWidget(self.tabs)
        engineering_actions = QHBoxLayout(); engineering_actions.addStretch()
        self.save_engineering_draft = QPushButton("Save draft"); self.complete_engineering = QPushButton("Complete")
        self.save_engineering_draft.setEnabled(False); self.complete_engineering.setEnabled(False)
        self.save_engineering_draft.clicked.connect(self._save_technical_card_draft); self.complete_engineering.clicked.connect(self._complete_technical_card)
        engineering_actions.addWidget(self.save_engineering_draft); engineering_actions.addWidget(self.complete_engineering); left.addLayout(engineering_actions)
        body.addLayout(left, 4)

        right = QVBoxLayout()
        self.summary = BlockSummaryWidget()
        self.photos = AttachmentPreviewWidget("Photos")
        self.documents = AttachmentPreviewWidget("Documents")
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
        dialog = BlockDialog(self.block_service, self.domain_repo, self.context.current_user, block=self.current_block)
        if dialog.exec():
            self.current_block = self.block_service.get_block(dialog.saved_block_id or self.current_block.id)
            self.refresh()
            self.data_changed.emit()

    def open_directories(self) -> None:
        self.refresh()
        self.data_changed.emit()

    def _render_current_block(self) -> None:
        block = self.current_block
        audit_entries = self.audit_repo.list_for_block(block.id) if block else []
        photos = self.attachment_repo.list_for_block(block.id, "photo", 5) if block else []
        documents = self.attachment_repo.list_for_block(block.id, "document", 5) if block else []
        photo_count = self.attachment_repo.count_for_block(block.id, "photo") if block else 0
        document_count = self.attachment_repo.count_for_block(block.id, "document") if block else 0
        self.header.set_block(block, self.context.current_user.can_edit)
        self.overview.set_block(block)
        self.compact_cards.set_block(block)
        self.comments.set_block(block)
        self.summary.set_data(block, photo_count, document_count, len(audit_entries))
        self.photos.set_items(photos, "No photos yet")
        self.documents.set_items(documents, "No documents yet")
        self.audit_preview.set_entries(audit_entries)
        self.history_tab.set_entries(audit_entries, limit=200)
        self._render_engineering(block)

    def _replace_tab(self, old, new, title):
        index=self.tabs.indexOf(old); self.tabs.removeTab(index); self.tabs.insertTab(index,new,title); return new

    def _render_engineering(self, block):
        if block is None:return
        self.entity_controller=EntityPageController(self.context,block.domain_id)
        event=self.entity_controller.event_for_block(block.id)
        if event is None:
            self.overview.scheme.set_geometry(None,context="Linked production geometry is not loaded")
            return
        geometry=event.active_geometry_revision(); dataset=self.entity_controller.state.active_dataset(); lines=dataset.lines if dataset else []
        self.overview.scheme.set_geometry(geometry.plan_geometry if geometry else None,lines,
            f"Horizon {event.elevation:g} | CSV: {geometry.source_file_name if geometry else '—'} | Revision: {geometry.revision_number if geometry else '—'}")
        try:self.overview.scheme.reimport_requested.disconnect()
        except RuntimeError:pass
        self.overview.scheme.reimport_requested.connect(lambda:self._reimport_geometry(event))
        card,revision=self.entity_controller.technical_card_draft(event)
        editor=TechnicalCardEditorWidget(event,card,revision,self.entity_controller.save_technical_card,self,not self.context.current_user.can_edit or block.is_archived)
        self.geomechanics_tab=self._replace_tab(self.geomechanics_tab,GeomechanicsEditorWidget(editor.take_tab("Геомеханика")),"Geomechanics")
        self.design_tab=self._replace_tab(self.design_tab,BlastDesignEditorWidget(editor.take_tab("Бурение и заряды")),"Blast design")
        self.execution_tab=self._replace_tab(self.execution_tab,ActualExecutionEditorWidget(editor.take_tab("Факт")),"Execution fact")
        self.technical_card_editor=editor
        self.save_engineering_draft.setEnabled(not editor.editor.read_only); self.complete_engineering.setEnabled(not editor.editor.read_only)

    def _save_technical_card_draft(self):
        if hasattr(self,"technical_card_editor"): self.technical_card_editor.save_draft()
    def _complete_technical_card(self):
        if hasattr(self,"technical_card_editor"): self.technical_card_editor.complete()

    def _reimport_geometry(self,event):
        path,_=QFileDialog.getOpenFileName(self,"Reimport production geometry","","CSV (*.csv)")
        if not path:return
        try:
            from prototype_2d.blast_event_service import BlastEventService
            BlastEventService(self.entity_controller.state).reimport_geometry(event,path); self.entity_controller.save(); self._render_engineering(self.current_block)
        except Exception as exc:QMessageBox.warning(self,"Geometry import",str(exc))
