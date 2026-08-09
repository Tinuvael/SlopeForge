from __future__ import annotations
from decimal import Decimal
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from repositories.blast_block_repository import BlastBlockRepository
from repositories.site_repository import SiteRepository
from repositories.domain_repository import DomainRepository
from repositories.navigation_repository import NavigationRepository
from app.icons.ui.ui_icons import ui_icon


def _number(value):
    text = format(Decimal(value).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text

class ProjectTree(QWidget):
    block_selected = Signal(int, int, int)
    site_selected = Signal(int, str)
    domain_selected = Signal(int, str, int, str)
    assessment_area_selected = Signal(str, int, int, str)
    contour_event_selected = Signal(str, int, int, str)
    def __init__(self, context):
        super().__init__(); self.context = context
        self.site_repo = SiteRepository(context.session_factory); self.domain_repo = DomainRepository(context.session_factory)
        self.block_repo = BlastBlockRepository(context.session_factory); self.navigation_repo = NavigationRepository(context.session_factory)
        layout = QVBoxLayout(self); layout.setContentsMargins(8,8,8,8); layout.addWidget(QLabel("Projects"))
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.itemClicked.connect(self._item_clicked); layout.addWidget(self.tree)
        layout.addWidget(QLabel("Filters"))
        self.search = QLineEdit(); self.search.setPlaceholderText("Search by block number")
        self.project_filter = QComboBox(); self.domain_filter = QComboBox(); self.status_filter = QComboBox()
        self.show_archived = QCheckBox("Show archived"); self.reset_button = QPushButton("Reset filters"); self.reset_button.setIcon(ui_icon("refresh"))
        for widget in (self.search, self.project_filter, self.domain_filter, self.status_filter,
                       self.show_archived, self.reset_button): layout.addWidget(widget)
        self.project_filter.currentIndexChanged.connect(self._reload_domains)
        for signal in (self.search.textChanged, self.domain_filter.currentIndexChanged,
                       self.status_filter.currentIndexChanged, self.show_archived.toggled): signal.connect(self.load_data)
        self.reset_button.clicked.connect(self.reset_filters)
        self.reload_filters()
        self.load_data()
    def reload_filters(self):
        selected = self.project_filter.currentData() if self.project_filter.count() else None
        self.project_filter.blockSignals(True); self.project_filter.clear(); self.project_filter.addItem("All projects", None)
        for site in self.site_repo.list_sites(): self.project_filter.addItem(site.name, site.id)
        self.project_filter.setCurrentIndex(max(0, self.project_filter.findData(selected))); self.project_filter.blockSignals(False)
        self.status_filter.clear(); self.status_filter.addItem("All statuses", None)
        for value, label in (("planned","Planned"),("blasted","Blasted"),("assessed","Assessed")): self.status_filter.addItem(label,value)
        self._reload_domains()
    def _reload_domains(self, *_args):
        selected = self.domain_filter.currentData() if self.domain_filter.count() else None
        self.domain_filter.blockSignals(True); self.domain_filter.clear(); self.domain_filter.addItem("All domains", None)
        sites = [self.project_filter.currentData()] if self.project_filter.currentData() else [s.id for s in self.site_repo.list_sites()]
        for site_id in sites:
            for domain in self.domain_repo.list_for_site(site_id): self.domain_filter.addItem(domain.name, domain.id)
        self.domain_filter.setCurrentIndex(max(0, self.domain_filter.findData(selected))); self.domain_filter.blockSignals(False); self.load_data()
    def reset_filters(self):
        self.search.clear(); self.project_filter.setCurrentIndex(0); self.status_filter.setCurrentIndex(0); self.show_archived.setChecked(False); self._reload_domains()
    def load_data(self, *_args, **_kwargs):
        self.tree.clear(); areas_by_domain = {}; contours_by_domain={}
        for area in self.navigation_repo.list_active_areas(): areas_by_domain.setdefault(area.domain_id, []).append(area)
        for event in self.navigation_repo.list_contour_events(self.show_archived.isChecked()): contours_by_domain.setdefault(event.domain_id,[]).append(event)
        project_id = self.project_filter.currentData(); domain_id = self.domain_filter.currentData()
        for site in self.site_repo.list_sites():
            if project_id is not None and site.id != project_id: continue
            site_item = self._item(site.name, {"type":"site","id":site.id,"site_name":site.name}); self.tree.addTopLevelItem(site_item)
            for domain in self.domain_repo.list_for_site(site.id):
                if domain_id is not None and domain.id != domain_id: continue
                base = {"domain_id":domain.id,"domain_name":domain.name,"site_id":site.id,"site_name":site.name}
                domain_item = self._item(domain.name, {"type":"domain", **base}); site_item.addChild(domain_item)
                blocks_folder = self._item("Blast events", {"type":"folder", **base}); domain_item.addChild(blocks_folder)
                horizons = {}
                for block in self.block_repo.list_blocks(domain_id=domain.id, number_query=self.search.text(), status=self.status_filter.currentData(), show_archived=self.show_archived.isChecked()):
                    label = "No horizon" if block.horizon_m is None else f"Horizon {_number(block.horizon_m)}"
                    folder = horizons.get(label)
                    if folder is None: folder = self._item(label, {"type":"horizon", **base}); blocks_folder.addChild(folder); horizons[label] = folder
                    text = f"Block {block.block_number}" + (" [Archived]" if block.is_archived else "")
                    folder.addChild(self._item(text, {"type":"block","id":block.id,"archived":block.is_archived, **base}))
                for event in contours_by_domain.get(domain.id,[]):
                    if self.search.text().strip() and self.search.text().strip().lower() not in event.name.lower(): continue
                    label=f"Horizon {_number(event.elevation)}"; folder=horizons.get(label)
                    if folder is None: folder=self._item(label,{"type":"horizon",**base}); blocks_folder.addChild(folder); horizons[label]=folder
                    text=f"Contour {event.name}" + (" [Archived]" if event.is_archived else "")
                    folder.addChild(self._item(text,{"type":"contour","id":event.id,"archived":event.is_archived,**base}))
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
        item = QTreeWidgetItem([text]); item.setData(0, Qt.ItemDataRole.UserRole, payload)
        icons={"site":"mine","domain":"domain","folder":"blast-blocks" if text=="Blast events" else "assessment-area","horizon":"horizon","block":"block","contour":"contour","interval":"layers","area":"assessment-area"}
        item.setIcon(0,ui_icon(icons.get(payload.get("type"),"folder-open"))); return item
    def _item_clicked(self, item, _column=0):
        p = item.data(0, Qt.ItemDataRole.UserRole) or {}; kind = p.get("type")
        if kind in {"folder","horizon","interval"}: item.setExpanded(not item.isExpanded()); return
        if kind == "site": self.site_selected.emit(p["id"], p["site_name"])
        elif kind == "domain": self.domain_selected.emit(p["domain_id"], p["domain_name"], p["site_id"], p["site_name"])
        elif kind == "block": self.block_selected.emit(p["id"], p["domain_id"], p["site_id"])
        elif kind == "area": self.assessment_area_selected.emit(p["id"], p["domain_id"], p["site_id"], p["domain_name"])
        elif kind == "contour": self.contour_event_selected.emit(p["id"],p["domain_id"],p["site_id"],p["domain_name"])
