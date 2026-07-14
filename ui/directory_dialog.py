from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from database.app_context import CurrentUser
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository


class DirectoryDialog(QDialog):
    def __init__(self, mine_repo: MineRepository, site_repo: SiteRepository, user: CurrentUser):
        super().__init__()
        self.mine_repo = mine_repo
        self.site_repo = site_repo
        self.user = user
        self.selected_mine_id = None
        self.selected_site_id = None
        self.setWindowTitle("Справочники")
        self.resize(760, 520)
        layout = QVBoxLayout(self)
        tabs = QTabWidget(); layout.addWidget(tabs)
        tabs.addTab(self._mine_tab(), "Месторождения")
        tabs.addTab(self._site_tab(), "Участки")
        self.refresh_all()

    def _mine_tab(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w)
        self.mine_table = QTableWidget(0, 2); self.mine_table.setHorizontalHeaderLabels(["Название", "Описание"])
        self.mine_table.itemSelectionChanged.connect(self._select_mine)
        layout.addWidget(self.mine_table)
        form = QFormLayout(); self.mine_name = QLineEdit(); self.mine_desc = QTextEdit(); self.mine_desc.setMaximumHeight(70)
        form.addRow("Название *", self.mine_name); form.addRow("Описание", self.mine_desc); layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        add = QPushButton("Создать"); add.clicked.connect(self._save_new_mine)
        upd = QPushButton("Сохранить изменения"); upd.clicked.connect(self._update_mine)
        add.setEnabled(self.user.can_edit); upd.setEnabled(self.user.can_edit)
        buttons.addWidget(add); buttons.addWidget(upd); layout.addLayout(buttons)
        return w

    def _site_tab(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w)
        self.site_table = QTableWidget(0, 3); self.site_table.setHorizontalHeaderLabels(["Месторождение", "Участок", "Описание"])
        self.site_table.itemSelectionChanged.connect(self._select_site)
        layout.addWidget(self.site_table)
        form = QFormLayout(); self.site_mine = QComboBox(); self.site_name = QLineEdit(); self.site_desc = QTextEdit(); self.site_desc.setMaximumHeight(70)
        form.addRow("Месторождение *", self.site_mine); form.addRow("Название *", self.site_name); form.addRow("Описание", self.site_desc); layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        add = QPushButton("Создать"); add.clicked.connect(self._save_new_site)
        upd = QPushButton("Сохранить изменения"); upd.clicked.connect(self._update_site)
        add.setEnabled(self.user.can_edit); upd.setEnabled(self.user.can_edit)
        buttons.addWidget(add); buttons.addWidget(upd); layout.addLayout(buttons)
        return w

    def refresh_all(self) -> None:
        self.mines = self.mine_repo.list_mines(); self.sites = self.site_repo.list_sites()
        self.mine_table.setRowCount(len(self.mines))
        for row, mine in enumerate(self.mines):
            self.mine_table.setItem(row, 0, QTableWidgetItem(mine.name)); self.mine_table.setItem(row, 1, QTableWidgetItem(mine.description or ""))
        self.site_mine.clear()
        for mine in self.mines:
            self.site_mine.addItem(mine.name, mine.id)
        self.site_table.setRowCount(len(self.sites))
        for row, site in enumerate(self.sites):
            self.site_table.setItem(row, 0, QTableWidgetItem(site.mine.name)); self.site_table.setItem(row, 1, QTableWidgetItem(site.name)); self.site_table.setItem(row, 2, QTableWidgetItem(site.description or ""))

    def _select_mine(self) -> None:
        row = self.mine_table.currentRow()
        if row < 0 or row >= len(self.mines): return
        mine = self.mines[row]; self.selected_mine_id = mine.id; self.mine_name.setText(mine.name); self.mine_desc.setPlainText(mine.description or "")

    def _select_site(self) -> None:
        row = self.site_table.currentRow()
        if row < 0 or row >= len(self.sites): return
        site = self.sites[row]; self.selected_site_id = site.id; self.site_name.setText(site.name); self.site_desc.setPlainText(site.description or "")
        idx = self.site_mine.findData(site.mine_id); self.site_mine.setCurrentIndex(max(idx, 0))

    def _save_new_mine(self) -> None:
        if not self.mine_name.text().strip(): QMessageBox.warning(self, "Проверьте данные", "Название обязательно."); return
        self.mine_repo.create_mine(self.mine_name.text(), self.mine_desc.toPlainText()); self.refresh_all()

    def _update_mine(self) -> None:
        if self.selected_mine_id is None: return
        self.mine_repo.update_mine(self.selected_mine_id, self.mine_name.text(), self.mine_desc.toPlainText()); self.refresh_all()

    def _save_new_site(self) -> None:
        if not self.site_name.text().strip(): QMessageBox.warning(self, "Проверьте данные", "Название участка обязательно."); return
        self.site_repo.create_site(self.site_mine.currentData(), self.site_name.text(), self.site_desc.toPlainText()); self.refresh_all()

    def _update_site(self) -> None:
        if self.selected_site_id is None: return
        self.site_repo.update_site(self.selected_site_id, self.site_mine.currentData(), self.site_name.text(), self.site_desc.toPlainText()); self.refresh_all()
