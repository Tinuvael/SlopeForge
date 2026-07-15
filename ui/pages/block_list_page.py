from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout, QWidget

from database.app_context import AppContext
from repositories.attachment_repository import AttachmentRepository
from repositories.audit_log_repository import AuditLogRepository
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
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


class BlockListPage(QWidget):
    data_changed = Signal()

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.mine_repo = MineRepository(context.session_factory)
        self.site_repo = SiteRepository(context.session_factory)
        self.block_repo = BlastBlockRepository(context.session_factory)
        self.block_service = BlastBlockService(self.block_repo, self.site_repo)
        self.audit_repo = AuditLogRepository(context.session_factory)
        self.attachment_repo = AttachmentRepository(context.session_factory)
        self.filters = {"number_query": None, "mine_id": None, "site_id": None, "status": None}
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
        self.tabs.addTab(EmptySection(), "Geomechanics")
        self.tabs.addTab(EmptySection(), "Blast design")
        self.tabs.addTab(EmptySection(), "Execution fact")
        self.tabs.addTab(EmptySection(), "Documents")
        self.history_tab = AuditPreviewWidget("Change history")
        self.tabs.addTab(self.history_tab, "History")
        left.addWidget(self.tabs)
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

    def create_block(self) -> None:
        dialog = BlockDialog(self.block_service, self.mine_repo, self.site_repo, self.context.current_user)
        if dialog.exec():
            self.current_block = self.block_service.get_block(dialog.saved_block_id) if dialog.saved_block_id else None
            self.refresh()
            self.data_changed.emit()

    def edit_current_block(self) -> None:
        if not self.current_block or not self.context.current_user.can_edit:
            return
        dialog = BlockDialog(self.block_service, self.mine_repo, self.site_repo, self.context.current_user, self.current_block)
        if dialog.exec():
            self.current_block = self.block_service.get_block(dialog.saved_block_id or self.current_block.id)
            self.refresh()
            self.data_changed.emit()

    def open_directories(self) -> None:
        dialog = DirectoryDialog(self.mine_repo, self.site_repo, self.context.current_user)
        dialog.exec()
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
