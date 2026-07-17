from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
<<<<<<< HEAD
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.app_context import CurrentUser
from repositories.audit_log_repository import AuditLogRepository
from repositories.blast_block_repository import BlastBlockRow
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
from services.blast_block_service import AUDIT_FIELD_LABELS, BlastBlockInput, BlastBlockService, PermissionDenied, STATUS_LABELS, ValidationError

ACTION_LABELS = {"create": "Создание", "update": "Изменение", "delete": "Удаление", "attach": "Прикрепление", "detach": "Открепление"}
=======
from PySide6.QtWidgets import QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout

from database.app_context import CurrentUser
from repositories.blast_block_repository import BlastBlockRow
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
from services.blast_block_service import BlastBlockInput, BlastBlockService, PermissionDenied, STATUS_LABELS, ValidationError
>>>>>>> origin/main


class BlockDialog(QDialog):
    def __init__(self, service: BlastBlockService, mine_repo: MineRepository, site_repo: SiteRepository, user: CurrentUser, block: BlastBlockRow | None = None, read_only: bool = False):
        super().__init__()
        self.service = service; self.mine_repo = mine_repo; self.site_repo = site_repo; self.user = user; self.block = block; self.saved_block_id = None
<<<<<<< HEAD
        self.audit_repo = AuditLogRepository(service.session_factory)
        self.read_only = read_only or not user.can_edit
        self.setWindowTitle("Block card" if block else "New block")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tabs.addTab(self._general_tab(), "Общая информация")
        self.tabs.addTab(self._history_tab(), "История изменений")

        buttons = QHBoxLayout(); buttons.addStretch(); cancel = QPushButton("Close" if self.read_only else "Cancel"); cancel.clicked.connect(self.reject); buttons.addWidget(cancel)
        self.save_button = QPushButton("Save"); self.save_button.clicked.connect(self._save); self.save_button.setVisible(not self.read_only); buttons.addWidget(self.save_button); layout.addLayout(buttons)
        self._load_mines(); self._fill_from_block(); self._set_read_only(); self.load_history()

    def _general_tab(self) -> QWidget:
        widget = QWidget(); form = QFormLayout(widget)
=======
        self.read_only = read_only or not user.can_edit
        self.setWindowTitle("Block card" if block else "New block")
        self.resize(520, 430)
        layout = QVBoxLayout(self); form = QFormLayout()
>>>>>>> origin/main
        self.block_number = QLineEdit(); self.mine = QComboBox(); self.site = QComboBox(); self.horizon = QLineEdit()
        self.planned_date = QDateEdit(); self.planned_date.setCalendarPopup(True); self.planned_date.setSpecialValueText(" "); self.planned_date.setMinimumDate(QDate(1900,1,1))
        self.status = QComboBox(); self.comment = QTextEdit()
        for value, label in STATUS_LABELS.items(): self.status.addItem(label, value)
        self.mine.currentIndexChanged.connect(self._load_sites)
        form.addRow("Block number *", self.block_number); form.addRow("Mine *", self.mine); form.addRow("Site *", self.site)
        form.addRow("Horizon, m", self.horizon); form.addRow("Planned blast date", self.planned_date); form.addRow("Status", self.status); form.addRow("Comment", self.comment)
<<<<<<< HEAD
        return widget

    def _history_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.empty_history = QLabel("История изменений отсутствует")
        self.history_table = QTableWidget(0, 7)
        self.history_table.setHorizontalHeaderLabels(["Дата и время", "Пользователь", "Действие", "Поле", "Старое значение", "Новое значение", "Описание"])
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.empty_history)
        layout.addWidget(self.history_table)
        return widget
=======
        layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch(); cancel = QPushButton("Close" if self.read_only else "Cancel"); cancel.clicked.connect(self.reject); buttons.addWidget(cancel)
        self.save_button = QPushButton("Save"); self.save_button.clicked.connect(self._save); self.save_button.setVisible(not self.read_only); buttons.addWidget(self.save_button); layout.addLayout(buttons)
        self._load_mines(); self._fill_from_block(); self._set_read_only()
>>>>>>> origin/main

    def _load_mines(self) -> None:
        self.mine.clear()
        for mine in self.mine_repo.list_mines(): self.mine.addItem(mine.name, mine.id)
        self._load_sites()

    def _load_sites(self) -> None:
        mine_id = self.mine.currentData(); self.site.clear()
        if mine_id is None: return
        for site in self.site_repo.list_sites(mine_id): self.site.addItem(site.name, site.id)

    def _fill_from_block(self) -> None:
        if not self.block: return
        self.block_number.setText(self.block.block_number); idx = self.mine.findData(self.block.mine_id); self.mine.setCurrentIndex(max(idx, 0)); self._load_sites()
        site_idx = self.site.findData(self.block.site_id); self.site.setCurrentIndex(max(site_idx, 0)); self.horizon.setText(str(self.block.horizon_m) if self.block.horizon_m is not None else "")
        if self.block.planned_blast_date:
            d = self.block.planned_blast_date; self.planned_date.setDate(QDate(d.year, d.month, d.day))
        else:
            self.planned_date.setDate(self.planned_date.minimumDate())
        status_idx = self.status.findData(self.block.status); self.status.setCurrentIndex(max(status_idx, 0)); self.comment.setPlainText(self.block.comment or "")

    def _set_read_only(self) -> None:
        for widget in [self.block_number, self.mine, self.site, self.horizon, self.planned_date, self.status, self.comment]: widget.setEnabled(not self.read_only)

    def _input(self) -> BlastBlockInput:
        qdate = self.planned_date.date(); planned = None if qdate == self.planned_date.minimumDate() else date(qdate.year(), qdate.month(), qdate.day())
        return BlastBlockInput(self.block_number.text(), self.mine.currentData(), self.site.currentData(), self.horizon.text(), planned, self.status.currentData(), self.comment.toPlainText())

<<<<<<< HEAD
    def load_history(self) -> None:
        if self.block is None:
            self.history_table.setRowCount(0); self.empty_history.setVisible(True); return
        entries = self.audit_repo.list_for_block(self.block.id)
        self.empty_history.setVisible(not entries)
        self.history_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                entry.created_at.strftime("%d.%m.%Y %H:%M:%S"),
                entry.user_display_name,
                ACTION_LABELS.get(entry.action, entry.action),
                AUDIT_FIELD_LABELS.get(entry.field_name or "", entry.field_name or ""),
                entry.old_value or "",
                entry.new_value or "",
                entry.description or "",
            ]
            for col, value in enumerate(values):
                self.history_table.setItem(row, col, QTableWidgetItem(value))

=======
>>>>>>> origin/main
    def _save(self) -> None:
        try:
            if self.block:
                self.saved_block_id = self.service.update_block(self.block.id, self._input(), self.user)
            else:
                self.saved_block_id = self.service.create_block(self._input(), self.user)
            self.accept()
        except (ValidationError, PermissionDenied, ValueError) as exc:
            QMessageBox.warning(self, "Could not save block", str(exc))
