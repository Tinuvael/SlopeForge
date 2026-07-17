from __future__ import annotations

<<<<<<< HEAD
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
=======
from PySide6.QtCore import Signal
>>>>>>> origin/main
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.app_context import AppContext
from repositories.blast_block_repository import BlastBlockRepository
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
from services.blast_block_service import BlastBlockService, STATUS_LABELS


<<<<<<< HEAD
def _horizon_label(horizon: Decimal | None) -> str:
    if horizon is None:
        return "No horizon"
    text = format(horizon.normalize(), "f")
    text = text.rstrip("0").rstrip(".") if "." in text else text
    return f"Horizon {text}"


class ProjectTree(QWidget):
    filters_changed = Signal(dict)
    block_selected = Signal(int)
=======
class ProjectTree(QWidget):
    filters_changed = Signal(dict)
>>>>>>> origin/main

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.mine_repo = MineRepository(context.session_factory)
        self.site_repo = SiteRepository(context.session_factory)
        self.block_service = BlastBlockService(BlastBlockRepository(context.session_factory), self.site_repo)

        layout = QVBoxLayout(self)
<<<<<<< HEAD
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
=======
>>>>>>> origin/main
        layout.addWidget(QLabel("Project"))

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
<<<<<<< HEAD
        self.tree.itemClicked.connect(self._item_clicked)
=======
>>>>>>> origin/main
        layout.addWidget(self.tree, 1)

        layout.addWidget(QLabel("Filters"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by block number")
        self.mine_filter = QComboBox()
        self.site_filter = QComboBox()
        self.status_filter = QComboBox()
        self.reset_button = QPushButton("Reset filters")

        for widget in (self.search, self.mine_filter, self.site_filter, self.status_filter, self.reset_button):
            layout.addWidget(widget)

        self.search.textChanged.connect(self._emit_filters)
        self.mine_filter.currentIndexChanged.connect(self._reload_site_filter)
        self.site_filter.currentIndexChanged.connect(self._emit_filters)
        self.status_filter.currentIndexChanged.connect(self._emit_filters)
        self.reset_button.clicked.connect(self.reset_filters)

        self.reload_filters()
        self.load_data()

    def reload_filters(self) -> None:
        current_mine = self.mine_filter.currentData() if self.mine_filter.count() else None
        current_site = self.site_filter.currentData() if self.site_filter.count() else None
        current_status = self.status_filter.currentData() if self.status_filter.count() else None

        self.mine_filter.blockSignals(True)
        self.mine_filter.clear()
        self.mine_filter.addItem("All mines", None)
        for mine in self.mine_repo.list_mines():
            self.mine_filter.addItem(mine.name, mine.id)
        self._restore_combo_value(self.mine_filter, current_mine)
        self.mine_filter.blockSignals(False)

        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self.status_filter.addItem("All statuses", None)
        for value, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, value)
        self._restore_combo_value(self.status_filter, current_status)
        self.status_filter.blockSignals(False)

        self._reload_site_filter(emit=False, preferred_site_id=current_site)

    def _reload_site_filter(self, emit: bool = True, preferred_site_id: int | None = None) -> None:
        current_site = preferred_site_id if preferred_site_id is not None else self.site_filter.currentData()
        self.site_filter.blockSignals(True)
        self.site_filter.clear()
        self.site_filter.addItem("All sites", None)
        for site in self.site_repo.list_sites(self.mine_filter.currentData()):
            self.site_filter.addItem(site.name, site.id)
        self._restore_combo_value(self.site_filter, current_site)
        self.site_filter.blockSignals(False)
        if emit:
            self._emit_filters()

    def reset_filters(self) -> None:
        self.search.clear()
        self.mine_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self._reload_site_filter(emit=False)
        self._emit_filters()

    def current_filters(self) -> dict:
        return {
            "number_query": self.search.text(),
            "mine_id": self.mine_filter.currentData(),
            "site_id": self.site_filter.currentData(),
            "status": self.status_filter.currentData(),
        }

    def _emit_filters(self) -> None:
        filters = self.current_filters()
        self.load_data(filters)
        self.filters_changed.emit(filters)

    def load_data(self, filters: dict | None = None) -> None:
        filters = filters or self.current_filters()
        self.tree.clear()
        mine_items: dict[int, QTreeWidgetItem] = {}
        site_items: dict[int, QTreeWidgetItem] = {}
<<<<<<< HEAD
        horizon_items: dict[tuple[int, str], QTreeWidgetItem] = {}
=======
>>>>>>> origin/main

        for mine in self.mine_repo.list_mines():
            if filters.get("mine_id") is not None and mine.id != filters["mine_id"]:
                continue
            mine_item = QTreeWidgetItem([mine.name])
<<<<<<< HEAD
            mine_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "mine", "id": mine.id})
=======
>>>>>>> origin/main
            self.tree.addTopLevelItem(mine_item)
            mine_items[mine.id] = mine_item

        for site in self.site_repo.list_sites(filters.get("mine_id")):
            if filters.get("site_id") is not None and site.id != filters["site_id"]:
                continue
            mine_item = mine_items.get(site.mine_id)
            if mine_item is None:
                continue
            site_item = QTreeWidgetItem([site.name])
<<<<<<< HEAD
            site_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "site", "id": site.id})
=======
>>>>>>> origin/main
            mine_item.addChild(site_item)
            site_items[site.id] = site_item

        for block in self.block_service.list_blocks(**filters):
            site_item = site_items.get(block.site_id)
<<<<<<< HEAD
            if site_item is None:
                continue
            horizon = _horizon_label(block.horizon_m)
            key = (block.site_id, horizon)
            horizon_item = horizon_items.get(key)
            if horizon_item is None:
                horizon_item = QTreeWidgetItem([horizon])
                horizon_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "horizon", "value": horizon})
                site_item.addChild(horizon_item)
                horizon_items[key] = horizon_item
            block_item = QTreeWidgetItem([f"Block {block.block_number}"])
            block_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "block", "id": block.id})
            horizon_item.addChild(block_item)

        self.tree.expandAll()

    def _item_clicked(self, item: QTreeWidgetItem) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if payload.get("type") == "block":
            self.block_selected.emit(int(payload["id"]))

=======
            if site_item is not None:
                site_item.addChild(QTreeWidgetItem([f"Block {block.block_number}"]))

        self.tree.expandAll()

>>>>>>> origin/main
    @staticmethod
    def _restore_combo_value(combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
