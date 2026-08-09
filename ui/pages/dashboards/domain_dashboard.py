
from app.localization import tr
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout,QHeaderView,QLabel,QScrollArea,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from app.icons.ui.ui_icons import ui_icon
from repositories.dashboard_repository import DashboardRepository
from .charts import CompactChart
from .plan_overview import DashboardPlanOverviewWidget
from .widgets import EmptyStateWidget,MetricCard,metric,quadrant_presentation,section

class DomainDashboardPage(QWidget):
    block_requested=Signal(int); contour_requested=Signal(str); assessment_area_requested=Signal(str)
    def __init__(self,context,domain_id,name=None):
        super().__init__(); self.snapshot=DashboardRepository(context.session_factory).domain_snapshot(domain_id); d=self.snapshot.domain
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
        scroll=QScrollArea(); scroll.setWidgetResizable(True); body=QWidget(); box=QVBoxLayout(body); box.addWidget(self._metrics()); box.addWidget(section(tr("Assessment areas by interval"),CompactChart(self.snapshot.intervals))); box.addWidget(section(tr("Result distribution"),CompactChart(self.snapshot.quadrants,"donut")))
        problem_areas=[a for a in self.snapshot.areas if a.status=="completed" and quadrant_presentation(a.quadrant).requires_attention]; problem_areas.sort(key=lambda a:quadrant_presentation(a.quadrant).severity,reverse=True)
        problems=[(a.name,a.interval,metric(a.dai),metric(a.fci),a.assessment_date or "—",quadrant_presentation(a.quadrant).label) for a in problem_areas[:6]]; table=self._table([tr("Area"),tr("Interval"),tr("DAI"),tr("FCI"),tr("Date"),tr("Result")],problems) if problems else EmptyStateWidget(tr("No areas requiring attention") ); box.addWidget(section(tr("Areas requiring attention"),table)); box.addWidget(section(tr("Recent changes"),self._table([tr("Record"),tr("Changed")],self.snapshot.recent) if self.snapshot.recent else EmptyStateWidget(tr("No recent activity")))); box.addWidget(section(tr("Plan overview"),DashboardPlanOverviewWidget(self.snapshot))); scroll.setWidget(body); return scroll
    def _blasts(self):
        rows=[(tr(x.entity_type),x.name,x.horizon,x.event_date or "—",tr(x.status.title())) for x in self.snapshot.blasts]; t=self._table([tr("Type"),tr("Block / event"),tr("Horizon"),tr("Date"),tr("Status")],rows); t.cellDoubleClicked.connect(lambda r,_: self.block_requested.emit(int(self.snapshot.blasts[r].id)) if self.snapshot.blasts[r].entity_type=="Production" else self.contour_requested.emit(str(self.snapshot.blasts[r].id))); return t
    def _areas(self):
        rows=[(x.name,x.interval,x.assessment_date or "—",tr(x.status.title()) if x.status else "—",metric(x.dai),metric(x.fci),quadrant_presentation(x.quadrant).label) for x in self.snapshot.areas]; t=self._table([tr("Area"),tr("Interval"),tr("Assessment date"),tr("Status"),tr("DAI"),tr("FCI"),tr("Result")],rows); t.cellDoubleClicked.connect(lambda r,_:self.assessment_area_requested.emit(self.snapshot.areas[r].id)); return t
    def _analytics(self):
        w=QWidget(); box=QVBoxLayout(w); box.addWidget(CompactChart(self.snapshot.intervals)); box.addWidget(CompactChart(self.snapshot.quadrants,"donut")); return w
