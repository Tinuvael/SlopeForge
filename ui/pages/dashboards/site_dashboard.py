
from app.localization import tr
from ui.presentation_labels import domain_message
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog,QGridLayout,QHeaderView,QLabel,QMessageBox,QPushButton,QScrollArea,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from app.icons.ui.ui_icons import ui_icon
from prototype_2d.domain import AssessmentDomainState
from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
from repositories.dashboard_repository import DashboardRepository
from repositories.project_lines_repository import ProjectLinesRepository
from .charts import CompactChart
from .widgets import EmptyStateWidget,MetricCard,metric,quadrant_presentation,section

class SiteDashboardPage(QWidget):
    domain_requested=Signal(int)
    def __init__(self,context,site_id,name):
        super().__init__(); self.context=context; self.site_id=site_id; self.repo=DashboardRepository(context.session_factory); self.lines_repo=ProjectLinesRepository(context.session_factory); self.snapshot=self.repo.site_snapshot(site_id)
        root=QVBoxLayout(self); title=QLabel(name); title.setStyleSheet("font-size:24px;font-weight:700;color:#0F172A"); root.addWidget(title); root.addWidget(QLabel(tr("Overall project overview"))); self.tabs=QTabWidget(); root.addWidget(self.tabs); self._populate_tabs()
    def _populate_tabs(self):
        while self.tabs.count():
            widget=self.tabs.widget(0); self.tabs.removeTab(0); widget.deleteLater()
        self.tabs.addTab(self._overview(),ui_icon("analytics"),tr("Overview")); self.tabs.addTab(self._domains(),ui_icon("domain"),tr("Domains")); self.tabs.addTab(self._lines(),ui_icon("project-lines"),tr("Project Lines")); self.tabs.addTab(self._analytics(),ui_icon("analytics"),tr("Analytics"))
    def refresh(self):
        current=self.tabs.currentIndex(); self.snapshot=self.repo.site_snapshot(self.site_id); self._populate_tabs(); self.tabs.setCurrentIndex(max(0,min(current,self.tabs.count()-1)))
    def _table(self,headers,rows,ids=None):
        table=QTableWidget(len(rows),len(headers)); table.setHorizontalHeaderLabels(headers); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r,row in enumerate(rows):
            for c,value in enumerate(row): table.setItem(r,c,QTableWidgetItem(str(value)))
            if ids: table.item(r,0).setData(32,ids[r])
        if ids: table.cellDoubleClicked.connect(lambda r,_:self.domain_requested.emit(int(table.item(r,0).data(32))))
        return table
    def _metrics(self):
        s=self.snapshot; w=QWidget(); g=QGridLayout(w); pct=round(100*s.completed/s.areas) if s.areas else 0
        event_detail = tr("Production: %1 • Contour: %2").replace("%1", str(s.production)).replace("%2", str(s.contour))
        evaluation_detail = tr("%1% • Drafts: %2").replace("%1", str(pct)).replace("%2", str(s.drafts))
        cards=[MetricCard(tr("Blast events"),s.production+s.contour,event_detail,"blast-blocks"),MetricCard(tr("Assessment areas"),s.areas,tr("Active areas"),"assessment-area"),MetricCard(tr("Evaluated"),f"{s.completed} / {s.areas}",evaluation_detail,"check"),MetricCard(tr("Average DAI"),metric(s.average_dai),tr("Completed evaluations"),"analytics"),MetricCard(tr("Average FCI"),metric(s.average_fci),tr("Completed evaluations"),"analytics")]
        for i,c in enumerate(cards): g.addWidget(c,0,i)
        return w
    def _domain_rows(self):
        return [(d.domain.name,d.domain.blast_events,d.domain.production,d.domain.contour,d.domain.areas,d.domain.completed,metric(d.domain.average_dai),metric(d.domain.average_fci)) for d in self.snapshot.domains]
    def _overview(self):
        page=QScrollArea(); page.setWidgetResizable(True); body=QWidget(); box=QVBoxLayout(body); box.addWidget(self._metrics()); table=self._table([tr("Domain"),tr("Blast events"),tr("Production"),tr("Contour"),tr("Assessment areas"),tr("Completed"),tr("Average DAI"),tr("Average FCI")],self._domain_rows(),[d.domain.id for d in self.snapshot.domains]); box.addWidget(section(tr("Domain summary"),table))
        quadrants={}; [quadrants.update({k:quadrants.get(k,0)+v}) for d in self.snapshot.domains for k,v in d.quadrants.items()]; box.addWidget(section(tr("Assessment result distribution"),CompactChart(quadrants,"donut")))
        problem_areas=[(a,d.domain.name) for d in self.snapshot.domains for a in d.areas if a.status=="completed" and quadrant_presentation(a.quadrant).requires_attention]; problem_areas.sort(key=lambda item:quadrant_presentation(item[0].quadrant).severity,reverse=True); problems=[(a.name,domain,a.interval,metric(a.dai),metric(a.fci),a.assessment_date or "—") for a,domain in problem_areas[:5]]; box.addWidget(section(tr("Areas requiring attention"),self._table([tr("Area"),tr("Domain"),tr("Interval"),tr("DAI"),tr("FCI"),tr("Date")],problems) if problems else EmptyStateWidget(tr("No areas requiring attention"))))
        recent=[(name,when or "—") for name,when in self.snapshot.recent]; box.addWidget(section(tr("Recent activity"),self._table([tr("Record"),tr("Changed")],recent) if recent else EmptyStateWidget(tr("No recent activity")))); page.setWidget(body); return page
    def _domains(self): return self._table([tr("Domain"),tr("Blast events"),tr("Production"),tr("Contour"),tr("Assessment areas"),tr("Completed"),tr("Average DAI"),tr("Average FCI")],self._domain_rows(),[d.domain.id for d in self.snapshot.domains])
    def _lines(self):
        w=QWidget(); box=QVBoxLayout(w); active=self.snapshot.active_dataset; box.addWidget(QLabel(f"{tr('Active Dataset')}: {active.name} • {active.source_file_name} • {active.imported_at:%Y-%m-%d %H:%M}" if active else tr("No Project Lines loaded"))); rows=[(x.name,x.imported_at.strftime("%Y-%m-%d %H:%M"),x.source_file_name,tr("Active") if x.is_active else tr("Inactive")) for x in self.snapshot.datasets]; box.addWidget(self._table([tr("Dataset"),tr("Imported"),tr("Source file"),tr("State")],rows)); self.import_button=QPushButton(tr("Import / Update Project Lines")); self.import_button.setIcon(ui_icon("import","blue")); self.import_button.setVisible(self.context.current_user.can_edit); self.import_button.clicked.connect(self.import_lines); box.addWidget(self.import_button); return w
    def _analytics(self):
        w=QWidget(); box=QVBoxLayout(w); box.addWidget(CompactChart({d.domain.name:d.domain.completed for d in self.snapshot.domains if d.domain.completed})); return w
    def import_lines(self):
        path,_=QFileDialog.getOpenFileName(self,"Datamine CSV — Project Lines","","CSV (*.csv)")
        if not path:return
        try: dataset,_=ProjectLinesDatasetService(AssessmentDomainState()).import_dataset(path); self.lines_repo.import_dataset(self.site_id,dataset,make_active=True); self.refresh()
        except Exception as exc: QMessageBox.warning(self,tr("Import error"),domain_message(str(exc)))
