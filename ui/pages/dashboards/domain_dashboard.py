
from app.localization import tr
from PySide6.QtCore import Signal
from pathlib import Path
from PySide6.QtWidgets import QFileDialog,QGridLayout,QHBoxLayout,QHeaderView,QLabel,QMessageBox,QPushButton,QScrollArea,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from app.icons.ui.ui_icons import ui_icon
from repositories.dashboard_repository import DashboardRepository
from repositories.domain_geometry_repository import DomainGeometryRepository
from domain.project.domain_geometry import build_domain_polygons
from infrastructure.geometry_import.lines import import_line_geometry
from ui.dialogs.domain_geometry_editor import DomainGeometryEditorDialog
from ui.presentation_labels import domain_message
from .charts import CompactChart
from .plan_overview import DashboardPlanOverviewWidget
from .widgets import EmptyStateWidget,MetricCard,metric,quadrant_presentation,section

class DomainDashboardPage(QWidget):
    block_requested=Signal(int); contour_requested=Signal(str); assessment_area_requested=Signal(str)
    def __init__(self,context,domain_id,name=None):
        super().__init__(); self.context=context; self.domain_id=domain_id; self.repo=DashboardRepository(context.session_factory); self.geometry_repo=DomainGeometryRepository(context.session_factory); self.snapshot=self.repo.domain_snapshot(domain_id); d=self.snapshot.domain
        root=QVBoxLayout(self); h=QLabel(name or d.name); h.setStyleSheet("font-size:24px;font-weight:700"); root.addWidget(h); root.addWidget(QLabel(tr("Domain overview"))); self.tabs=QTabWidget(); root.addWidget(self.tabs); self.tabs.addTab(self._overview(),ui_icon("analytics"),tr("Overview")); self.tabs.addTab(self._blasts(),ui_icon("blast-blocks"),tr("Blast events")); self.tabs.addTab(self._areas(),ui_icon("assessment-area"),tr("Assessment areas")); self.tabs.addTab(self._analytics(),ui_icon("analytics"),tr("Analytics")); self.tabs.addTab(DashboardPlanOverviewWidget(self.snapshot),ui_icon("map"),tr("Map"))
    def _table(self,headers,rows):
        t=QTableWidget(len(rows),len(headers)); t.setHorizontalHeaderLabels(headers); t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r,row in enumerate(rows):
            for c,v in enumerate(row): t.setItem(r,c,QTableWidgetItem(str(v)))
        return t
    def _metrics(self):
        d=self.snapshot.domain; w=QWidget(); g=QGridLayout(w); pct=round(100*d.completed/d.areas) if d.areas else 0
        event_detail = tr("Production: %1 • Contour: %2").replace("%1", str(d.production)).replace("%2", str(d.contour))
        evaluation_detail = tr("%1% • Drafts: %2").replace("%1", str(pct)).replace("%2", str(d.drafts))
        for i,c in enumerate([MetricCard(tr("Blast events"),d.blast_events,event_detail,"blast-blocks"),MetricCard(tr("Assessment areas"),d.areas,tr("Active areas"),"assessment-area"),MetricCard(tr("Evaluated"),f"{d.completed} / {d.areas}",evaluation_detail,"check"),MetricCard(tr("Average DAI"),metric(d.average_dai),tr("Completed"),"analytics"),MetricCard(tr("Average FCI"),metric(d.average_fci),tr("Completed"),"analytics")]):g.addWidget(c,0,i)
        return w
    def _overview(self):
        scroll=QScrollArea(); scroll.setWidgetResizable(True); body=QWidget(); box=QVBoxLayout(body); box.addWidget(self._metrics()); box.addWidget(self._geometry_card()); box.addWidget(section(tr("Assessment areas by interval"),CompactChart(self.snapshot.intervals))); box.addWidget(section(tr("Result distribution"),CompactChart(self.snapshot.quadrants,"donut")))
        problem_areas=[a for a in self.snapshot.areas if a.status=="completed" and quadrant_presentation(a.quadrant).requires_attention]; problem_areas.sort(key=lambda a:quadrant_presentation(a.quadrant).severity,reverse=True)
        problems=[(a.name,a.interval,metric(a.dai),metric(a.fci),a.assessment_date or "—",quadrant_presentation(a.quadrant).label) for a in problem_areas[:6]]; table=self._table([tr("Area"),tr("Interval"),tr("DAI"),tr("FCI"),tr("Date"),tr("Result")],problems) if problems else EmptyStateWidget(tr("No areas requiring attention") ); box.addWidget(section(tr("Areas requiring attention"),table)); box.addWidget(section(tr("Recent changes"),self._table([tr("Record"),tr("Changed")],self.snapshot.recent) if self.snapshot.recent else EmptyStateWidget(tr("No recent activity")))); box.addWidget(section(tr("Plan overview"),DashboardPlanOverviewWidget(self.snapshot))); scroll.setWidget(body); return scroll
    def _blasts(self):
        rows=[(tr(x.entity_type),x.name,x.horizon,x.event_date or "—",tr(x.status.title())) for x in self.snapshot.blasts]; t=self._table([tr("Type"),tr("Block / event"),tr("Horizon"),tr("Date"),tr("Status")],rows); t.cellDoubleClicked.connect(lambda r,_: self.block_requested.emit(int(self.snapshot.blasts[r].id)) if self.snapshot.blasts[r].entity_type=="Production" else self.contour_requested.emit(str(self.snapshot.blasts[r].id))); return t
    def _areas(self):
        rows=[(x.name,x.interval,x.assessment_date or "—",tr(x.status.title()) if x.status else "—",metric(x.dai),metric(x.fci),quadrant_presentation(x.quadrant).label) for x in self.snapshot.areas]; t=self._table([tr("Area"),tr("Interval"),tr("Assessment date"),tr("Status"),tr("DAI"),tr("FCI"),tr("Result")],rows); t.cellDoubleClicked.connect(lambda r,_:self.assessment_area_requested.emit(self.snapshot.areas[r].id)); return t
    def _analytics(self):
        w=QWidget(); box=QVBoxLayout(w); box.addWidget(CompactChart(self.snapshot.intervals)); box.addWidget(CompactChart(self.snapshot.quadrants,"donut")); return w
    def _geometry_card(self):
        w=QWidget(); box=QVBoxLayout(w); current=[g for g in self.snapshot.domain_geometries if g.is_current]
        box.addWidget(QLabel(tr("%1 polygons").replace("%1",str(len(current))) if current else tr("No geometry defined")))
        if current:
            source=self.snapshot.geometry_source_file_name or tr("Drawn"); box.addWidget(QLabel(tr("Source: %1").replace("%1",source)))
        buttons=QHBoxLayout(); self.import_geometry_button=QPushButton(tr("Replace / Import") if current else tr("Import geometry")); self.draw_geometry_button=QPushButton(tr("Edit boundaries") if current else tr("Draw geometry")); self.clear_geometry_button=QPushButton(tr("Clear geometry"));
        can_edit=getattr(getattr(self.context,"current_user",None),"can_edit",False)
        for button in (self.import_geometry_button,self.draw_geometry_button,self.clear_geometry_button): buttons.addWidget(button); button.setVisible(can_edit)
        self.clear_geometry_button.setVisible(bool(current) and can_edit); buttons.addStretch(); box.addLayout(buttons)
        self.import_geometry_button.clicked.connect(self.import_geometry); self.draw_geometry_button.clicked.connect(self.edit_geometry); self.clear_geometry_button.clicked.connect(self.clear_geometry)
        return section(tr("Domain geometry"),w)
    def _refresh(self):
        self.snapshot=self.repo.domain_snapshot(self.domain_id)
        # Rebuild only tab contents; this also refreshes both map instances.
        current=self.tabs.currentIndex()
        while self.tabs.count(): widget=self.tabs.widget(0); self.tabs.removeTab(0); widget.deleteLater()
        self.tabs.addTab(self._overview(),ui_icon("analytics"),tr("Overview")); self.tabs.addTab(self._blasts(),ui_icon("blast-blocks"),tr("Blast events")); self.tabs.addTab(self._areas(),ui_icon("assessment-area"),tr("Assessment areas")); self.tabs.addTab(self._analytics(),ui_icon("analytics"),tr("Analytics")); self.tabs.addTab(DashboardPlanOverviewWidget(self.snapshot),ui_icon("map"),tr("Map")); self.tabs.setCurrentIndex(current)
    def import_geometry(self):
        path,_=QFileDialog.getOpenFileName(self,tr("Select Domain geometry file"),"",tr("Geometry files (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"))
        if not path:return
        try:
            imported=import_line_geometry(path); result=build_domain_polygons(imported.lines); self.geometry_repo.replace_imported(self.domain_id,result.polygons,Path(path).name); self._refresh()
            text="\n".join((tr("File: %1").replace("%1",Path(path).name),tr("Imported polygons: %1").replace("%1",str(len(result.polygons))),tr("Skipped open lines: %1").replace("%1",str(result.skipped_open_lines)),tr("Skipped degenerate lines: %1").replace("%1",str(result.skipped_degenerate_lines))))
            QMessageBox.information(self,tr("Domain geometry"),text)
        except Exception as exc: QMessageBox.warning(self,tr("Import error"),domain_message(str(exc)))
    def edit_geometry(self):
        stored=self.geometry_repo.get_for_domain(self.domain_id); dialog=DomainGeometryEditorDialog(stored.polygons if stored else (),self.snapshot.project_lines,self)
        if dialog.exec(): self.geometry_repo.replace_drawn(self.domain_id,dialog.polygons); self._refresh()
    def clear_geometry(self):
        if QMessageBox.question(self,tr("Clear geometry"),tr("Clear the current Domain geometry?"))==QMessageBox.StandardButton.Yes:
            self.geometry_repo.clear(self.domain_id); self._refresh()
