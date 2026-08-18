from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.localization import tr
from PySide6.QtCore import QDate, QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QFormLayout,
                               QHBoxLayout, QLabel, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)
from repositories.production_blast_repository import ProductionBlastRepository
from repositories.domain_repository import DomainRepository
from repositories.navigation_repository import NavigationRepository
from repositories.site_repository import SiteRepository
from app.icons.ui.ui_icons import ui_icon


def _number(value):
    text = format(Decimal(value).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class OptionalDateEdit(QDateEdit):
    """Native date editor whose minimum/special value represents no boundary."""

    UNSET = QDate(1752, 9, 14)

    def __init__(self):
        super().__init__()
        self.setCalendarPopup(True)
        self.setMinimumDate(self.UNSET)
        self.setSpecialValueText(tr("Not set"))
        self.calendarWidget().installEventFilter(self)
        self.clear_date()

    def clear_date(self):
        self.setDate(self.minimumDate())
        self._show_current_calendar_page_if_unset()

    def value(self) -> date | None:
        return None if self.date() == self.minimumDate() else self.date().toPython()

    def set_value(self, value: date | None):
        self.setDate(self.minimumDate() if value is None else QDate(value.year, value.month, value.day))
        if value is None:
            self._show_current_calendar_page_if_unset()

    def eventFilter(self, watched, event):
        if watched is self.calendarWidget() and event.type() == QEvent.Type.Show and self.value() is None:
            QTimer.singleShot(0, self._show_current_calendar_page_if_unset)
        return super().eventFilter(watched, event)

    def _show_current_calendar_page_if_unset(self):
        if self.value() is None:
            today = QDate.currentDate()
            self.calendarWidget().setCurrentPage(today.year(), today.month())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.clear_date()
            event.accept()
            return
        super().keyPressEvent(event)


class ProjectTreeWidget(QTreeWidget):
    """Tree whose virtual grouping rows stay expanded but draw no disclosure arrow."""

    VIRTUAL_SECTION_TYPES = {"horizon", "interval"}

    def drawBranches(self, painter, rect, index):
        payload = index.data(Qt.ItemDataRole.UserRole) or {}
        if isinstance(payload, dict) and payload.get("type") in self.VIRTUAL_SECTION_TYPES:
            return
        super().drawBranches(painter, rect, index)


class ProjectTree(QWidget):
    block_selected = Signal(str, int, int)
    site_selected = Signal(int, str)
    domain_selected = Signal(int, str, int, str)
    assessment_area_selected = Signal(str, int, int, str)
    contour_event_selected = Signal(str, int, int, str)
    reset_search_requested = Signal()

    _VIRTUAL_SECTION_TYPES = ProjectTreeWidget.VIRTUAL_SECTION_TYPES

    def __init__(self, context):
        super().__init__(); self.context = context; self._search_query = ""
        self.site_repo = SiteRepository(context.session_factory); self.domain_repo = DomainRepository(context.session_factory)
        self.block_repo = ProductionBlastRepository(context.session_factory); self.navigation_repo = NavigationRepository(context.session_factory)
        layout = QVBoxLayout(self); layout.setContentsMargins(8,8,8,8)
        tree_header = QHBoxLayout(); tree_header.setContentsMargins(0,0,0,0)
        self.tree_title = QLabel(tr("Project tree"))
        self.collapse_button = QPushButton(); self.collapse_button.setObjectName("collapseProjectTreeButton")
        self.collapse_button.setIcon(ui_icon("collapse")); self.collapse_button.setFixedSize(30,26)
        self.collapse_button.setToolTip(tr("Collapse domains")); self.collapse_button.setAccessibleName(self.collapse_button.toolTip())
        tree_header.addWidget(self.tree_title); tree_header.addStretch(); tree_header.addWidget(self.collapse_button); layout.addLayout(tree_header)
        self.tree = ProjectTreeWidget(); self.tree.setHeaderHidden(True); self.tree.itemClicked.connect(self._item_clicked); self.tree.itemCollapsed.connect(self._keep_virtual_section_expanded); layout.addWidget(self.tree)
        self.collapse_button.clicked.connect(self.collapse_domains)
        layout.addWidget(QLabel(tr("Filters")))
        self.project_filter = QComboBox(); self.domain_filter = QComboBox(); self.status_filter = QComboBox()
        self.from_date = OptionalDateEdit(); self.to_date = OptionalDateEdit()
        form = QFormLayout(); form.setContentsMargins(0, 0, 0, 0); form.setSpacing(5)
        form.addRow(tr("Project"), self.project_filter); form.addRow(tr("Domain"), self.domain_filter)
        form.addRow(tr("Status"), self.status_filter); form.addRow(tr("From"), self.from_date); form.addRow(tr("To"), self.to_date)
        layout.addLayout(form)
        self.show_archived = QCheckBox(tr("Show archived")); self.reset_button = QPushButton(tr("Reset filters")); self.reset_button.setIcon(ui_icon("refresh"))
        layout.addWidget(self.show_archived); layout.addWidget(self.reset_button)
        self.project_filter.currentIndexChanged.connect(self._project_changed)
        for signal in (self.domain_filter.currentIndexChanged, self.status_filter.currentIndexChanged,
                       self.from_date.dateChanged, self.to_date.dateChanged, self.show_archived.toggled):
            signal.connect(self.load_data)
        self.reset_button.clicked.connect(self.reset_filters)
        self.reload_filters(); self.load_data()

    @property
    def search_query(self):
        return self._search_query

    def set_search_query(self, text):
        query = (text or "").strip().casefold()
        if query != self._search_query:
            self._search_query = query
            self.load_data()

    def reload_filters(self):
        selected_project = self.project_filter.currentData() if self.project_filter.count() else None
        selected_status = self.status_filter.currentData() if self.status_filter.count() else None
        self.project_filter.blockSignals(True); self.status_filter.blockSignals(True)
        self.project_filter.clear(); self.project_filter.addItem(tr("All projects"), None)
        for site in self.site_repo.list_sites(): self.project_filter.addItem(site.name, site.id)
        self.project_filter.setCurrentIndex(max(0, self.project_filter.findData(selected_project)))
        self.status_filter.clear(); self.status_filter.addItem(tr("All statuses"), None)
        for value, label in (("in_preparation","In preparation"),("planned","Planned"),("blasted","Blasted"),("assessed","Assessed")):
            self.status_filter.addItem(tr(label), value)
        self.status_filter.setCurrentIndex(max(0, self.status_filter.findData(selected_status)))
        self.project_filter.blockSignals(False); self.status_filter.blockSignals(False)
        self._reload_domains(refresh=False)

    def _project_changed(self, *_args):
        self._reload_domains(refresh=True)

    def _reload_domains(self, *, preserve=True, refresh=True):
        selected = self.domain_filter.currentData() if preserve and self.domain_filter.count() else None
        self.domain_filter.blockSignals(True); self.domain_filter.clear(); self.domain_filter.addItem(tr("All domains"), None)
        site_ids = [self.project_filter.currentData()] if self.project_filter.currentData() else [s.id for s in self.site_repo.list_sites()]
        for site_id in site_ids:
            for domain in self.domain_repo.list_for_site(site_id): self.domain_filter.addItem(domain.name, domain.id)
        self.domain_filter.setCurrentIndex(max(0, self.domain_filter.findData(selected)))
        self.domain_filter.blockSignals(False)
        if refresh: self.load_data()

    def reset_filters(self):
        controls = (self.project_filter, self.domain_filter, self.status_filter,
                    self.from_date, self.to_date, self.show_archived)
        for control in controls: control.blockSignals(True)
        self._search_query = ""; self.project_filter.setCurrentIndex(0); self.status_filter.setCurrentIndex(0)
        self.from_date.clear_date(); self.to_date.clear_date(); self.show_archived.setChecked(False)
        self._reload_domains(preserve=False, refresh=False)
        for control in controls: control.blockSignals(False)
        self.reset_search_requested.emit(); self.load_data()

    def _date_matches(self, value):
        start, end = self.from_date.value(), self.to_date.value()
        if (start or end) and value is None: return False
        return not ((start and value < start) or (end and value > end))

    def collapse_domains(self):
        """Keep Project rows visible and collapse only their Domain children."""
        for project_index in range(self.tree.topLevelItemCount()):
            project = self.tree.topLevelItem(project_index)
            project.setExpanded(True)
            for domain_index in range(project.childCount()):
                domain = project.child(domain_index)
                payload = domain.data(0, Qt.ItemDataRole.UserRole) or {}
                if payload.get("type") == "domain":
                    domain.setExpanded(False)
        self._expand_virtual_sections()

    def _keep_virtual_section_expanded(self, item):
        payload = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if payload.get("type") in self._VIRTUAL_SECTION_TYPES:
            QTimer.singleShot(0, lambda target=item: target.setExpanded(True))

    def _expand_virtual_sections(self):
        def visit(item):
            payload = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if payload.get("type") in self._VIRTUAL_SECTION_TYPES:
                item.setExpanded(True)
            for index in range(item.childCount()): visit(item.child(index))
        for index in range(self.tree.topLevelItemCount()): visit(self.tree.topLevelItem(index))

    def load_data(self, *_args, **_kwargs):
        self.tree.clear(); query = self._search_query
        show_archived = self.show_archived.isChecked(); status = self.status_filter.currentData()
        areas_by_domain, contours_by_domain = {}, {}
        for area in self.navigation_repo.list_areas(show_archived): areas_by_domain.setdefault(area.domain_id, []).append(area)
        for event in self.navigation_repo.list_contour_events(show_archived): contours_by_domain.setdefault(event.domain_id, []).append(event)
        project_id, domain_id = self.project_filter.currentData(), self.domain_filter.currentData()
        constrained = bool(query or status or self.from_date.value() or self.to_date.value())
        for site in self.site_repo.list_sites():
            if project_id is not None and site.id != project_id: continue
            site_match = bool(query and query in site.name.casefold())
            site_item = self._item(site.name, {"type":"site","id":site.id,"site_name":site.name})
            for domain in self.domain_repo.list_for_site(site.id):
                if domain_id is not None and domain.id != domain_id: continue
                domain_match = bool(query and query in domain.name.casefold())
                inherited_match = site_match or domain_match
                base = {"domain_id":domain.id,"domain_name":domain.name,"site_id":site.id,"site_name":site.name}
                domain_item = self._item(domain.name, {"type":"domain", **base})
                blasts = []
                for block in self.block_repo.list_blocks(domain_id=domain.id, status=status, show_archived=show_archived):
                    if self._date_matches(block.planned_blast_date) and (not query or inherited_match or query in block.block_number.casefold()):
                        blasts.append(("block", block.horizon_m, block))
                for event in contours_by_domain.get(domain.id, []):
                    if status and event.status != status: continue
                    if self._date_matches(event.event_date) and (not query or inherited_match or query in event.name.casefold()):
                        blasts.append(("contour", event.elevation, event))
                areas = [area for area in areas_by_domain.get(domain.id, [])
                         if self._date_matches(area.assessment_date)
                         and (not query or inherited_match or query in area.name.casefold())]
                include_domain = bool(blasts or areas or (not constrained) or (inherited_match and not (status or self.from_date.value() or self.to_date.value())))
                if not include_domain: continue
                site_item.addChild(domain_item)
                if blasts or not constrained:
                    folder = self._item(tr("Blast events"), {"type":"folder","folder_kind":"blast_events", **base}); domain_item.addChild(folder)
                    horizons = {}
                    for kind, elevation, row in blasts:
                        label = tr("No horizon") if elevation is None else f"{tr('Horizon')} {_number(elevation)}"
                        horizon = horizons.get(label)
                        if horizon is None: horizon=self._item(label,{"type":"horizon",**base}); folder.addChild(horizon); horizons[label]=horizon
                        if kind == "block": text=f"{tr('Block')} {row.block_number}"; payload={"type":"block","id":row.id,"archived":row.is_archived,**base}
                        else: text=f"{tr('Contour')} {row.name}"; payload={"type":"contour","id":row.id,"archived":row.is_archived,**base}
                        if row.is_archived: text += f" [{tr('Archived')}]"
                        horizon.addChild(self._item(text,payload))
                if areas or not constrained:
                    folder = self._item(tr("Assessment areas"), {"type":"folder","folder_kind":"assessment_areas", **base}); domain_item.addChild(folder)
                    intervals={}
                    for area in areas:
                        label=f"{tr('Interval')} {_number(area.min_elevation) if area.min_elevation is not None else '—'}–{_number(area.max_elevation) if area.max_elevation is not None else '—'}"
                        interval=intervals.get(label)
                        if interval is None: interval=self._item(label,{"type":"interval",**base}); folder.addChild(interval); intervals[label]=interval
                        text=area.name + (f" [{tr('Archived')}]" if area.is_archived else "")
                        interval.addChild(self._item(text,{"type":"area","id":area.id,"archived":area.is_archived,**base}))
            if site_item.childCount() or not constrained or site_match:
                self.tree.addTopLevelItem(site_item)
        self.tree.expandAll() if constrained else self.tree.expandToDepth(1)
        self._expand_virtual_sections()
        QTimer.singleShot(0, self._expand_virtual_sections)

    @staticmethod
    def _item(text, payload):
        item=QTreeWidgetItem([text]); item.setData(0,Qt.ItemDataRole.UserRole,payload)
        icons={"site":"mine","domain":"domain","folder":"blast-blocks" if payload.get("folder_kind")=="blast_events" else "assessment-area","horizon":"horizon","block":"block","contour":"contour","interval":"layers","area":"assessment-area"}
        item.setIcon(0,ui_icon(icons.get(payload.get("type"),"folder-open")))
        if payload.get("type") in ProjectTree._VIRTUAL_SECTION_TYPES:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = item.font(0); font.setBold(True); item.setFont(0, font)
        if payload.get("archived"): item.setForeground(0,Qt.GlobalColor.gray)
        return item

    def _item_clicked(self, item, _column=0):
        p=item.data(0,Qt.ItemDataRole.UserRole) or {}; kind=p.get("type")
        if kind in self._VIRTUAL_SECTION_TYPES:
            item.setExpanded(True); return
        if kind=="folder": item.setExpanded(not item.isExpanded()); return
        if kind=="site": self.site_selected.emit(p["id"],p["site_name"])
        elif kind=="domain": self.domain_selected.emit(p["domain_id"],p["domain_name"],p["site_id"],p["site_name"])
        elif kind=="block": self.block_selected.emit(p["id"],p["domain_id"],p["site_id"])
        elif kind=="area": self.assessment_area_selected.emit(p["id"],p["domain_id"],p["site_id"],p["domain_name"])
        elif kind=="contour": self.contour_event_selected.emit(p["id"],p["domain_id"],p["site_id"],p["domain_name"])
