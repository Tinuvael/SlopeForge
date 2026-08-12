from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import pytest

from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.project.project_lines import ProjectLinesDataset

try:
    from PySide6.QtWidgets import QApplication
    from repositories.dashboard_repository import AreaRow,BlastRow,DomainDashboardSnapshot,DomainSummary,MapGeometry,SiteDashboardSnapshot,_project_line_geometries
    from ui.pages.dashboards.charts import CompactChart
    from ui.pages.dashboards.domain_dashboard import DomainDashboardPage
    from ui.pages.dashboards.plan_overview import DashboardPlanOverviewWidget
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}",allow_module_level=True)

SEPARATED_PARTS = Path(__file__).parent / "fixtures" / "project_lines_separated_parts.csv"

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

def test_project_line_parts_survive_import_serialization_projection_and_render(app):
    imported, _ = ProjectLinesDatasetService(AssessmentDomainState()).import_dataset(
        SEPARATED_PARTS, imported_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    reloaded = ProjectLinesDataset.from_dict(imported.to_dict())
    persisted_row = SimpleNamespace(lines_json=[line.to_dict() for line in reloaded.lines])
    projected = _project_line_geometries(persisted_row)

    assert [geometry.entity_id for geometry in projected] == ["WEST", "EAST"]
    assert [geometry.points for geometry in projected] == [
        ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)),
        ((1000.0, 1000.0), (1010.0, 1000.0), (1010.0, 1010.0)),
    ]

    plan = DashboardPlanOverviewWidget(
        DomainDashboardSnapshot(DomainSummary(7, "North"), project_lines=projected)
    )
    assert len(plan._project_items) == 2
    assert [item.path().elementCount() for item in plan._project_items] == [3, 3]
    assert all(not item.path().isClosed() for item in plan._project_items)
