from pathlib import Path
from types import SimpleNamespace

import pytest


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_project_and_domain_dashboards_are_single_non_scrolling_overviews():
    project = source("ui/pages/dashboards/site_dashboard.py")
    domain = source("ui/pages/dashboards/domain_dashboard.py")

    for page in (project, domain):
        assert "QTabWidget" not in page
        assert "QScrollArea" not in page
        assert "QTableWidget" not in page
        assert "DashboardPlanCard" in page
        assert "MetricCard" in page
        assert "DashboardRecentActivityCard" in page
        assert "CompactSummaryList" in page
        assert 'CompactSummaryList(\n            "Attention required", visible_rows=3' in page

    assert "ProjectLinesCard" in project
    assert 'primary_action_label="Project Lines"' in project
    assert 'CompactSummaryList("Domain summary", visible_rows=4)' in project
    assert "AssessmentProgressCard" in project
    assert "assessment_area_requested = Signal(str, int)" in project

    assert 'CompactSummaryList("Elevation intervals", visible_rows=4)' in domain
    assert '"Latest assessments", visible_rows=3' in domain
    assert "BlastActivityCard" in domain
    assert 'primary_action_label="Import geometry"' in domain
    assert 'secondary_action_label="Draw geometry"' in domain


def test_dashboard_plan_is_compact_assessment_focused_and_uses_1_5x_framing():
    plan = source("ui/pages/dashboards/plan_overview.py")
    assert "FRAME_FACTOR = 1.5" in plan
    assert "self.view.setMinimumHeight(185)" in plan
    assert "self.setMinimumHeight(230)" in plan
    assert "self.setMaximumHeight(310)" in plan
    assert 'getattr(self.snapshot, "assessment_geometries", ())' in plan
    assert 'getattr(self.snapshot, "project_lines", ())' in plan
    assert 'getattr(self.snapshot, "domain_geometries", ())' in plan
    assert "production_geometries" not in plan
    assert "contour_geometries" not in plan
    assert "assessment_result_presentation" in plan
    assert "DAI:" in plan and "FCI:" in plan


def test_dashboard_projection_uses_only_current_completed_assessment_result():
    repository = source("repositories/dashboard_repository.py")
    assert 'current_completed = status == "completed"' in repository
    assert "quadrant=row.quadrant if row else None" in repository
    assert "dai=row.dai if row else None" in repository
    assert "fci=row.fci if row else None" in repository
    assert "def assessment_geometries(self)" in repository


def test_dashboard_result_palette_matches_full_assessment_matrix():
    from ui.assessment_result_presentation import ASSESSMENT_RESULT_PRESENTATIONS

    expected = {
        "geometry_achieved_condition_insufficient": "#f6df72",
        "good_results": "#8bd17c",
        "unacceptable": "#ef7770",
        "condition_good_geometry_unacceptable": "#f2b764",
    }
    assert {
        key: value.color for key, value in ASSESSMENT_RESULT_PRESENTATIONS.items()
    } == expected

    editor = source("ui/editors/assessment_evaluation_editor.py")
    for colour in expected.values():
        assert colour in editor


def test_dashboard_internal_lists_are_bounded_and_card_styled():
    widgets = source("ui/pages/dashboards/widgets.py")
    assert "visible_rows: int = 4" in widgets
    assert "self.visible_rows" in widgets
    assert "DashboardSummaryRow" in widgets
    assert "ProjectLinesDatasetRow" in widgets
    assert "DASHBOARD_CARD_STYLE" in widgets
    assert "ScrollBarAsNeeded" in widgets
    assert "ScrollBarAlwaysOff" in widgets


def test_attention_uses_existing_assessment_result_severity_not_new_scoring():
    project = source("ui/pages/dashboards/site_dashboard.py")
    domain = source("ui/pages/dashboards/domain_dashboard.py")
    for page in (project, domain):
        assert "presentation.requires_attention" in page
        assert "presentation.severity" in page
        assert "assessment_result_presentation(area.quadrant)" in page
        assert "risk_score" not in page.lower()


def test_plan_focus_rect_expands_assessment_bounds_only():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    gui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    from ui.assessment_result_presentation import assessment_result_presentation
    from ui.pages.dashboards.plan_overview import DashboardPlanOverviewWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    assessment = SimpleNamespace(
        entity_id="AA-001",
        points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        quadrant="good_results",
        name="Area 1",
        domain_name="North",
        interval="600–630",
        dai=0.75,
        fci=0.80,
    )
    far_line = SimpleNamespace(
        entity_id="PL-1",
        points=((-1000.0, 0.0), (1000.0, 0.0)),
    )
    snapshot = SimpleNamespace(
        domain_geometries=(),
        project_lines=(far_line,),
        assessment_geometries=(assessment,),
    )
    plan = DashboardPlanOverviewWidget(snapshot)
    base = plan._items_rect(plan._assessment_items)
    focus = plan.focus_rect()

    assert focus.width() == pytest.approx(base.width() * 1.5)
    assert focus.height() == pytest.approx(base.height() * 1.5)
    assert focus.width() < 100
    assert len(plan._project_items) == 1
    assert "DAI: 0.75" in plan._assessment_items[0].toolTip()
    assert "FCI: 0.80" in plan._assessment_items[0].toolTip()
    expected_colour = gui.QColor(
        assessment_result_presentation("good_results").color
    )
    assert plan._assessment_items[0].pen().color() == expected_colour

    plan.close()
    app.processEvents()
