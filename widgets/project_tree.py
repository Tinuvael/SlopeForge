from __future__ import annotations
from decimal import Decimal
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from repositories.blast_block_repository import BlastBlockRepository
from repositories.site_repository import SiteRepository
from repositories.domain_repository import DomainRepository
from repositories.navigation_repository import NavigationRepository


def _number(value):
    text = format(Decimal(value).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text

class ProjectTree(QWidget):
    block_selected = Signal(int, int, int)
    site_selected = Signal(int, str)
    domain_selected = Signal(int, str, int, str)
    project_lines_selected = Signal(int, str)
    assessment_area_selected = Signal(str, int, int, str)
    def __init__(self, context):
        super().__init__(); self.context = context
        self.site_repo = SiteRepository(context.session_factory); self.domain_repo = DomainRepository(context.session_factory)
        self.block_repo = BlastBlockRepository(context.session_factory); self.navigation_repo = NavigationRepository(context.session_factory)
        layout = QVBoxLayout(self); layout.setContentsMargins(8,8,8,8); layout.addWidget(QLabel("Projects"))
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.itemClicked.connect(self._item_clicked); layout.addWidget(self.tree)
        self.load_data()
    def load_data(self, *_args, **_kwargs):
        self.tree.clear(); areas_by_domain = {}
        for area in self.navigation_repo.list_active_areas(): areas_by_domain.setdefault(area.domain_id, []).append(area)
        for site in self.site_repo.list_sites():
            site_item = self._item(site.name, {"type":"site","id":site.id,"site_name":site.name}); self.tree.addTopLevelItem(site_item)
            site_item.addChild(self._item("Project Lines", {"type":"project_lines","site_id":site.id,"site_name":site.name}))
            for domain in self.domain_repo.list_for_site(site.id):
                base = {"domain_id":domain.id,"domain_name":domain.name,"site_id":site.id,"site_name":site.name}
                domain_item = self._item(domain.name, {"type":"domain", **base}); site_item.addChild(domain_item)
                blocks_folder = self._item("Blast blocks", {"type":"folder", **base}); domain_item.addChild(blocks_folder)
                horizons = {}
                for block in self.block_repo.list_blocks(domain_id=domain.id):
                    label = "No horizon" if block.horizon_m is None else f"Horizon {_number(block.horizon_m)}"
                    folder = horizons.get(label)
                    if folder is None: folder = self._item(label, {"type":"horizon", **base}); blocks_folder.addChild(folder); horizons[label] = folder
                    folder.addChild(self._item(f"Block {block.block_number}", {"type":"block","id":block.id, **base}))
                areas_folder = self._item("Assessment areas", {"type":"folder", **base}); domain_item.addChild(areas_folder)
                intervals = {}
                for area in areas_by_domain.get(domain.id, []):
                    label = f"Interval {_number(area.lower_elevation)}–{_number(area.upper_elevation)}"
                    folder = intervals.get(label)
                    if folder is None: folder = self._item(label, {"type":"interval", **base}); areas_folder.addChild(folder); intervals[label] = folder
                    folder.addChild(self._item(area.name, {"type":"area","id":area.id, **base}))
        self.tree.expandToDepth(1)
    @staticmethod
    def _item(text, payload):
        item = QTreeWidgetItem([text]); item.setData(0, Qt.ItemDataRole.UserRole, payload); return item
    def _item_clicked(self, item, _column=0):
        p = item.data(0, Qt.ItemDataRole.UserRole) or {}; kind = p.get("type")
        if kind in {"folder","horizon","interval"}: item.setExpanded(not item.isExpanded()); return
        if kind == "site": self.site_selected.emit(p["id"], p["site_name"])
        elif kind == "project_lines": self.project_lines_selected.emit(p["site_id"], p["site_name"])
        elif kind == "domain": self.domain_selected.emit(p["domain_id"], p["domain_name"], p["site_id"], p["site_name"])
        elif kind == "block": self.block_selected.emit(p["id"], p["domain_id"], p["site_id"])
        elif kind == "area": self.assessment_area_selected.emit(p["id"], p["domain_id"], p["site_id"], p["domain_name"])
