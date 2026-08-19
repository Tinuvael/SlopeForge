from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.project.project_lines import ProjectLinesDataset

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from repositories.dashboard_repository import (
        AreaRow,
        BlastRow,
        DomainDashboardSnapshot,
        DomainSummary,
        MapGeometry,
        SiteDashboardSnapshot,
        _project_line_geometries,
    )
    from ui.pages.dashboards.charts import CompactChart
    from ui.pages.dashboards.domain_dashboard import DomainDashboardPage
    from ui.pages.dashboards.site_dashboard import SiteDashboardPage
    from ui.pages.dashboards.plan_overview import (
        DashboardPlanCard,
        DashboardPlanOverviewWidget,
    )
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

SEPARATED_PARTS = Path(__file__).parent / "fixtures" / "project_lines_separated_parts.csv"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def snapshot():
    domain = DomainSummary(7, "North", 1, 1, 1, 1, 0, .8, .7)
    return DomainDashboardSnapshot(
        domain,
        [AreaRow("AREA-42", "A", "10–20", date.today(), "completed", .8, .7, "unacceptable")],
        [
            BlastRow(99, "Production", "B1", "10", None, "planned"),
            BlastRow("EVENT-55", "Contour", "C1", "10", None, "—"),
        ],
        {"10–20": 1},
        {"unacceptable": 1},
        [],
        (MapGeometry("line", ((0, 0), (20, 0))),),
        (MapGeometry(99, ((0, 0), (10, 0), (10, 10), (0, 0))),),
        (MapGeometry("EVENT-55", ((4, 4), (8, 8))),),
        (
            MapGeometry(
                "AREA-42",
                ((1, 1), (5, 1), (5, 5), (1, 1)),
                "unacceptable",
                "A",
                "North",
                "10–20",
                .8,
                .7,
            ),
        ),
    )


def _stub_domain_version(monkeypatch):
    monkeypatch.setattr(
        "ui.pages.dashboards.domain_dashboard.DomainGeometryRepository.get_domain_version",
        lambda *_args: 0,
    )


def test_native_charts_construct_with_and_without_data(app):
    assert CompactChart({"North": 2}).data
    assert CompactChart({}).data == {}


def test_project_domain_summary_emits_real_domain_id(app, monkeypatch):
    snap = snapshot()
    site_snap = SiteDashboardSnapshot(3, [snap], None, [])
    monkeypatch.setattr(
        "ui.pages.dashboards.site_dashboard.DashboardRepository.site_snapshot",
        lambda *_: site_snap,
    )
    context = SimpleNamespace(
        session_factory=lambda: None,
        current_user=SimpleNamespace(can_edit=False, id=1),
    )
    page = SiteDashboardPage(context, 3, "North Pit")
    received = []
    page.domain_requested.connect(received.append)

    item = page.domain_summary.list.item(0)
    page.domain_summary.list.itemClicked.emit(item)

    assert received == [7]
    page.close()


def test_domain_interval_summary_is_compact_and_not_entity_table(app, monkeypatch):
    snap = snapshot()
    monkeypatch.setattr(
        "ui.pages.dashboards.domain_dashboard.DashboardRepository.domain_snapshot",
        lambda *_: snap,
    )
    _stub_domain_version(monkeypatch)
    context = SimpleNamespace(
        session_factory=lambda: None,
        current_user=SimpleNamespace(can_edit=False, id=1),
    )
    page = DomainDashboardPage(context, 7, "North")

    assert page.interval_summary.list.count() == 1
    holder = page.interval_summary.list.itemWidget(page.interval_summary.list.item(0))
    assert holder is not None
    assert "10–20 m" in " ".join(label.text() for label in holder.findChildren(type(page.title_label)))
    assert not hasattr(page, "tabs")
    page.close()


@pytest.mark.parametrize("can_edit", [False, True])
def test_dashboard_rename_headers_are_real_widgets_and_refresh(app, monkeypatch, can_edit):
    snap = snapshot()
    site_snap = SiteDashboardSnapshot(3, [snap], None, [])
    monkeypatch.setattr(
        "ui.pages.dashboards.domain_dashboard.DashboardRepository.domain_snapshot",
        lambda *_: snap,
    )
    monkeypatch.setattr(
        "ui.pages.dashboards.site_dashboard.DashboardRepository.site_snapshot",
        lambda *_: site_snap,
    )
    _stub_domain_version(monkeypatch)
    context = SimpleNamespace(
        session_factory=lambda: None,
        current_user=SimpleNamespace(can_edit=can_edit, id=1),
    )
    site = SiteDashboardPage(context, 3, "North Pit")
    domain = DomainDashboardPage(context, 7, "North")
    assert site.title_label.text() == "North Pit" and site.edit_button.isEnabled() is can_edit
    assert domain.title_label.text() == "North" and domain.edit_button.isEnabled() is can_edit
    site.apply_rename_result(3, "Central Pit")
    domain.apply_rename_result(7, "East Wall", domain.expected_version + 1)
    assert site.title_label.text() == "Central Pit"
    assert domain.title_label.text() == "East Wall"
    site.close()
    domain.close()


def test_read_only_map_constructs_empty_and_populated(app):
    empty = DomainDashboardSnapshot(DomainSummary(7, "North"))
    empty_map = DashboardPlanOverviewWidget(empty)
    assert not empty_map.scene.items()

    plan = DashboardPlanOverviewWidget(snapshot())
    assert plan.scene.items()
    assert len(plan._assessment_items) == 1
    assert len(plan._project_items) == 1
    assert not hasattr(plan, "draw_button")
    assert not hasattr(plan, "edit_button")
    assert not hasattr(plan, "confirm_button")

    card = DashboardPlanCard(snapshot(), primary_action_label="Import geometry")
    assert card.center_button.text() == "Center"
    assert card.lines.text() == "Project Lines"
    assert card.primary_action.text() == "Import geometry"
    assert card.plan.view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert card.plan.view.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    empty_map.close()
    plan.close()
    card.close()


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
    for item in plan._project_items:
        path = item.path()
        first = path.elementAt(0)
        last = path.elementAt(path.elementCount() - 1)
        assert (first.x, first.y) != (last.x, last.y)
    plan.close()
