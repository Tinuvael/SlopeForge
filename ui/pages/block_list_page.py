from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from database.app_context import AppContext
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
from services.blast_block_service import BlastBlockService, STATUS_LABELS
from ui.block_dialog import BlockDialog
from ui.directory_dialog import DirectoryDialog


class BlockListPage(QWidget):
    data_changed = Signal()

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.mine_repo = MineRepository(context.session_factory); self.site_repo = SiteRepository(context.session_factory)
        self.block_repo = BlastBlockRepository(context.session_factory); self.block_service = BlastBlockService(self.block_repo, self.site_repo)
        self.rows: list[BlastBlockRow] = []
        layout = QVBoxLayout(self)
        self.filters = {"number_query": None, "mine_id": None, "site_id": None, "status": None}
        controls = QHBoxLayout()
        self.new_button = QPushButton("New block"); self.open_button = QPushButton("Open"); self.edit_button = QPushButton("Edit"); self.refresh_button = QPushButton("Refresh"); self.dict_button = QPushButton("Directories")
        for w in [self.new_button, self.open_button, self.edit_button, self.refresh_button, self.dict_button]: controls.addWidget(w)
        controls.addStretch()
        layout.addLayout(controls)
        self.table = QTableWidget(0, 9); self.table.setHorizontalHeaderLabels(["Block number", "Mine", "Site", "Horizon, m", "Planned blast date", "Status", "Author", "Created", "Updated"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.new_button.clicked.connect(self.create_block); self.open_button.clicked.connect(self.open_block); self.edit_button.clicked.connect(self.edit_block); self.refresh_button.clicked.connect(self.refresh); self.dict_button.clicked.connect(self.open_directories)
        self.table.doubleClicked.connect(self.open_block)
        self.new_button.setEnabled(context.current_user.can_edit); self.edit_button.setEnabled(context.current_user.can_edit)
        self.refresh()

    def set_filters(self, filters: dict) -> None:
        self.filters = filters
        self.refresh()

    def refresh(self) -> None:
        self.rows = self.block_service.list_blocks(**self.filters)
        self.table.setRowCount(len(self.rows))
        for row, item in enumerate(self.rows):
            values = [item.block_number, item.mine_name, item.site_name, str(item.horizon_m or ""), item.planned_blast_date.isoformat() if item.planned_blast_date else "", STATUS_LABELS.get(item.status, item.status), item.author_name or "", item.created_at.strftime("%Y-%m-%d %H:%M"), item.updated_at.strftime("%Y-%m-%d %H:%M")]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value); cell.setData(Qt.ItemDataRole.UserRole, item.id); self.table.setItem(row, col, cell)

    def selected_block(self) -> BlastBlockRow | None:
        row = self.table.currentRow()
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def create_block(self) -> None:
        dialog = BlockDialog(self.block_service, self.mine_repo, self.site_repo, self.context.current_user)
        if dialog.exec(): self.refresh(); self.data_changed.emit(); self._select_id(dialog.saved_block_id)

    def open_block(self) -> None:
        block = self.selected_block()
        if block: BlockDialog(self.block_service, self.mine_repo, self.site_repo, self.context.current_user, block, read_only=True).exec()

    def edit_block(self) -> None:
        block = self.selected_block()
        if not block: return
        dialog = BlockDialog(self.block_service, self.mine_repo, self.site_repo, self.context.current_user, block)
        if dialog.exec(): self.refresh(); self.data_changed.emit(); self._select_id(dialog.saved_block_id)

    def open_directories(self) -> None:
        dialog = DirectoryDialog(self.mine_repo, self.site_repo, self.context.current_user)
        dialog.exec(); self.refresh(); self.data_changed.emit()

    def _select_id(self, block_id: int | None) -> None:
        if block_id is None: return
        for row, item in enumerate(self.rows):
            if item.id == block_id: self.table.selectRow(row); return
