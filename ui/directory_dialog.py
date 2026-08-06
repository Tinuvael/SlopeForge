from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from database.app_context import CurrentUser
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
from repositories.domain_repository import DomainRepository


class DirectoryDialog(QDialog):
    def __init__(self, mine_repo: MineRepository, site_repo: SiteRepository, user: CurrentUser):
        super().__init__()
        self.mine_repo = mine_repo
        self.site_repo = site_repo
        self.user = user
        self.domain_repo = DomainRepository(site_repo.session_factory)
        self.selected_domain_id = None
        self.selected_mine_id = None
        self.selected_site_id = None
        self.setWindowTitle("Directories")
        self.resize(760, 520)
        layout = QVBoxLayout(self)
        tabs = QTabWidget(); layout.addWidget(tabs)
        tabs.addTab(self._mine_tab(), "Mines")
        tabs.addTab(self._site_tab(), "Sites")
        tabs.addTab(self._domain_tab(), "Domains")
        self.refresh_all()

    def _mine_tab(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w)
        self.mine_table = QTableWidget(0, 2); self.mine_table.setHorizontalHeaderLabels(["Name", "Description"])
        self.mine_table.itemSelectionChanged.connect(self._select_mine)
        layout.addWidget(self.mine_table)
        form = QFormLayout(); self.mine_name = QLineEdit(); self.mine_desc = QTextEdit(); self.mine_desc.setMaximumHeight(70)
        form.addRow("Name *", self.mine_name); form.addRow("Description", self.mine_desc); layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        add = QPushButton("Create"); add.clicked.connect(self._save_new_mine)
        upd = QPushButton("Save changes"); upd.clicked.connect(self._update_mine)
        add.setEnabled(self.user.can_edit); upd.setEnabled(self.user.can_edit)
        buttons.addWidget(add); buttons.addWidget(upd); layout.addLayout(buttons)
        return w

    def _site_tab(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w)
        self.site_table = QTableWidget(0, 3); self.site_table.setHorizontalHeaderLabels(["Mine", "Site", "Description"])
        self.site_table.itemSelectionChanged.connect(self._select_site)
        layout.addWidget(self.site_table)
        form = QFormLayout(); self.site_mine = QComboBox(); self.site_name = QLineEdit(); self.site_desc = QTextEdit(); self.site_desc.setMaximumHeight(70)
        form.addRow("Mine *", self.site_mine); form.addRow("Name *", self.site_name); form.addRow("Description", self.site_desc); layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        add = QPushButton("Create"); add.clicked.connect(self._save_new_site)
        upd = QPushButton("Save changes"); upd.clicked.connect(self._update_site)
        add.setEnabled(self.user.can_edit); upd.setEnabled(self.user.can_edit)
        buttons.addWidget(add); buttons.addWidget(upd); layout.addLayout(buttons)
        return w

    def _domain_tab(self) -> QWidget:
        w=QWidget(); layout=QVBoxLayout(w)
        self.domain_table=QTableWidget(0,3); self.domain_table.setHorizontalHeaderLabels(["Site","Domain","Description"]); self.domain_table.itemSelectionChanged.connect(self._select_domain); layout.addWidget(self.domain_table)
        form=QFormLayout(); self.domain_site=QComboBox(); self.domain_name=QLineEdit(); self.domain_desc=QTextEdit(); self.domain_desc.setMaximumHeight(70)
        form.addRow("Site *",self.domain_site); form.addRow("Name *",self.domain_name); form.addRow("Description",self.domain_desc); layout.addLayout(form)
        buttons=QHBoxLayout(); buttons.addStretch(); add=QPushButton("Create"); update=QPushButton("Save changes"); add.setEnabled(self.user.can_edit); update.setEnabled(self.user.can_edit); add.clicked.connect(self._save_new_domain); update.clicked.connect(self._update_domain); buttons.addWidget(add); buttons.addWidget(update); layout.addLayout(buttons); return w

    def refresh_all(self) -> None:
        self.mines = self.mine_repo.list_mines(); self.sites = self.site_repo.list_sites(); self.domains = self.domain_repo.list_domains()
        self.mine_table.setRowCount(len(self.mines))
        for row, mine in enumerate(self.mines):
            self.mine_table.setItem(row, 0, QTableWidgetItem(mine.name)); self.mine_table.setItem(row, 1, QTableWidgetItem(mine.description or ""))
        self.site_mine.clear()
        for mine in self.mines:
            self.site_mine.addItem(mine.name, mine.id)
        self.domain_site.clear()
        for site in self.sites: self.domain_site.addItem(site.name, site.id)
        self.domain_table.setRowCount(len(self.domains))
        for row, domain in enumerate(self.domains):
            self.domain_table.setItem(row,0,QTableWidgetItem(domain.site.name)); self.domain_table.setItem(row,1,QTableWidgetItem(domain.name)); self.domain_table.setItem(row,2,QTableWidgetItem(domain.description or ""))
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
        if not self.mine_name.text().strip(): QMessageBox.warning(self, "Check input", "Name is required."); return
        self.mine_repo.create_mine(self.mine_name.text(), self.mine_desc.toPlainText()); self.refresh_all()

    def _update_mine(self) -> None:
        if self.selected_mine_id is None: return
        self.mine_repo.update_mine(self.selected_mine_id, self.mine_name.text(), self.mine_desc.toPlainText()); self.refresh_all()

    def _save_new_site(self) -> None:
        if not self.site_name.text().strip(): QMessageBox.warning(self, "Check input", "Site name is required."); return
        self.site_repo.create_site(self.site_mine.currentData(), self.site_name.text(), self.site_desc.toPlainText()); self.refresh_all()

    def _update_site(self) -> None:
        if self.selected_site_id is None: return
        self.site_repo.update_site(self.selected_site_id, self.site_mine.currentData(), self.site_name.text(), self.site_desc.toPlainText()); self.refresh_all()

    def _select_domain(self):
        row=self.domain_table.currentRow()
        if row < 0 or row >= len(self.domains): return
        domain=self.domains[row]; self.selected_domain_id=domain.id; self.domain_name.setText(domain.name); self.domain_desc.setPlainText(domain.description or ""); self.domain_site.setCurrentIndex(max(self.domain_site.findData(domain.site_id),0))
    def _save_new_domain(self):
        if not self.user.can_edit: return
        self.domain_repo.create_domain(self.domain_site.currentData(), self.domain_name.text(), self.domain_desc.toPlainText()); self.refresh_all()
    def _update_domain(self):
        if not self.user.can_edit or self.selected_domain_id is None: return
        self.domain_repo.update_domain(self.selected_domain_id, self.domain_site.currentData(), self.domain_name.text(), self.domain_desc.toPlainText()); self.refresh_all()
