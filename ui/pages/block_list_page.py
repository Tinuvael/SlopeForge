from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from database.app_context import AppContext
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
from services.blast_block_service import BlastBlockService, STATUS_LABELS
from ui.block_dialog import BlockDialog
from ui.directory_dialog import DirectoryDialog


class BlockListPage(QWidget):
    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.mine_repo = MineRepository(context.session_factory); self.site_repo = SiteRepository(context.session_factory)
        self.block_repo = BlastBlockRepository(context.session_factory); self.block_service = BlastBlockService(self.block_repo, self.site_repo)
        self.rows: list[BlastBlockRow] = []
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.new_button = QPushButton("Новый блок"); self.open_button = QPushButton("Открыть"); self.edit_button = QPushButton("Редактировать"); self.refresh_button = QPushButton("Обновить"); self.dict_button = QPushButton("Справочники")
        self.search = QLineEdit(); self.search.setPlaceholderText("Поиск по номеру блока")
        self.mine_filter = QComboBox(); self.site_filter = QComboBox(); self.status_filter = QComboBox()
        for w in [self.new_button, self.open_button, self.edit_button, self.refresh_button, self.dict_button, self.search, self.mine_filter, self.site_filter, self.status_filter]: controls.addWidget(w)
        layout.addLayout(controls)
        self.table = QTableWidget(0, 9); self.table.setHorizontalHeaderLabels(["Номер блока", "Месторождение", "Участок", "Горизонт, м", "Плановая дата", "Статус", "Автор", "Создан", "Изменён"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.new_button.clicked.connect(self.create_block); self.open_button.clicked.connect(self.open_block); self.edit_button.clicked.connect(self.edit_block); self.refresh_button.clicked.connect(self.refresh); self.dict_button.clicked.connect(self.open_directories)
        self.search.textChanged.connect(self.refresh); self.mine_filter.currentIndexChanged.connect(self._reload_site_filter); self.site_filter.currentIndexChanged.connect(self.refresh); self.status_filter.currentIndexChanged.connect(self.refresh); self.table.doubleClicked.connect(self.open_block)
        self.new_button.setEnabled(context.current_user.can_edit); self.edit_button.setEnabled(context.current_user.can_edit)
        self._load_filters(); self.refresh()

    def _load_filters(self) -> None:
        self.mine_filter.blockSignals(True); self.mine_filter.clear(); self.mine_filter.addItem("Все месторождения", None)
        for mine in self.mine_repo.list_mines(): self.mine_filter.addItem(mine.name, mine.id)
        self.mine_filter.blockSignals(False)
        self.status_filter.clear(); self.status_filter.addItem("Все статусы", None)
        for value, label in STATUS_LABELS.items(): self.status_filter.addItem(label, value)
        self._reload_site_filter()

    def _reload_site_filter(self) -> None:
        self.site_filter.blockSignals(True); self.site_filter.clear(); self.site_filter.addItem("Все участки", None)
        for site in self.site_repo.list_sites(self.mine_filter.currentData()): self.site_filter.addItem(site.name, site.id)
        self.site_filter.blockSignals(False); self.refresh()

    def refresh(self) -> None:
        self.rows = self.block_service.list_blocks(number_query=self.search.text(), mine_id=self.mine_filter.currentData(), site_id=self.site_filter.currentData(), status=self.status_filter.currentData())
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
        if dialog.exec(): self._load_filters(); self.refresh(); self._select_id(dialog.saved_block_id)

    def open_block(self) -> None:
        block = self.selected_block()
        if block: BlockDialog(self.block_service, self.mine_repo, self.site_repo, self.context.current_user, block, read_only=True).exec()

    def edit_block(self) -> None:
        block = self.selected_block()
        if not block: return
        dialog = BlockDialog(self.block_service, self.mine_repo, self.site_repo, self.context.current_user, block)
        if dialog.exec(): self.refresh(); self._select_id(dialog.saved_block_id)

    def open_directories(self) -> None:
        dialog = DirectoryDialog(self.mine_repo, self.site_repo, self.context.current_user)
        dialog.exec(); self._load_filters(); self.refresh()

    def _select_id(self, block_id: int | None) -> None:
        if block_id is None: return
        for row, item in enumerate(self.rows):
            if item.id == block_id: self.table.selectRow(row); return
