from datetime import date
from types import SimpleNamespace
import pytest

try:
    from PySide6.QtWidgets import QApplication
    from repositories.dashboard_repository import AreaRow,BlastRow,DomainDashboardSnapshot,DomainSummary,MapGeometry,SiteDashboardSnapshot
    from ui.pages.dashboards.charts import CompactChart
    from ui.pages.dashboards.domain_dashboard import DomainDashboardPage
    from ui.pages.dashboards.plan_overview import DashboardPlanOverviewWidget
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}",allow_module_level=True)

@pytest.fixture(scope="module")
def app(): return QApplication.instance() or QApplication([])

def snapshot():
    domain=DomainSummary(7,"North",1,1,1,1,0,.8,.7)
    return DomainDashboardSnapshot(domain,[AreaRow("AREA-42","A","10–20",date.today(),"completed",.8,.7,"unacceptable")],[BlastRow(99,"Production","B1","10",None,"planned"),BlastRow("EVENT-55","Contour","C1","10",None,"—")],{"10–20":1},{"unacceptable":1},[],(MapGeometry("line",((0,0),(20,0))),),(MapGeometry(99,((0,0),(10,0),(10,10),(0,0))),),(MapGeometry("EVENT-55",((4,4),(8,8))),),(MapGeometry("AREA-42",((1,1),(5,1),(5,5),(1,1)),"unacceptable"),))

def test_native_charts_construct_with_and_without_data(app):
    assert CompactChart({"North":2}).data
    assert CompactChart({}).data=={}

def test_domain_rows_emit_real_entity_ids(app,monkeypatch):
    snap=snapshot(); monkeypatch.setattr("ui.pages.dashboards.domain_dashboard.DashboardRepository.domain_snapshot",lambda *_:snap)
    page=DomainDashboardPage(SimpleNamespace(session_factory=lambda:None),7)
    received=[]; page.block_requested.connect(lambda value:received.append(value)); page.contour_requested.connect(lambda value:received.append(value)); page.assessment_area_requested.connect(lambda value:received.append(value))
    blasts=page.tabs.widget(1); blasts.cellDoubleClicked.emit(0,0); blasts.cellDoubleClicked.emit(1,0)
    areas=page.tabs.widget(2); areas.cellDoubleClicked.emit(0,0)
    assert received==[99,"EVENT-55","AREA-42"]

def test_read_only_map_constructs_empty_and_populated(app):
    empty=DomainDashboardSnapshot(DomainSummary(7,"North")); empty_map=DashboardPlanOverviewWidget(empty); assert not empty_map.scene.items()
    plan=DashboardPlanOverviewWidget(snapshot()); assert plan.scene.items(); assert plan.fit_button.text()=="Fit"; assert plan.project_lines_checkbox.text()=="Project Lines"
    assert not hasattr(plan,"draw_button") and not hasattr(plan,"edit_button") and not hasattr(plan,"confirm_button")
