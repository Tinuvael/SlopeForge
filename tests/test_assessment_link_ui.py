from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication
    from ui.pages.assessment_area_page import AssessmentAreaPage
    from ui.pages.plan_geometry_widget import PlanGeometryWidget
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

from application.services.assessment_event_links import AssessmentEventLinkService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.entities import AssessmentArea
from domain.blasting.entities import BlastEvent
from domain.geometry.types import PlanPoint, PlanPolygon
from tests.assessment_boundary_fixtures import geometry_revision


def polygon(*coordinates):
    points = tuple(PlanPoint(*xy) for xy in coordinates)
    return PlanPolygon(points + (points[0],))


def scenario():
    area_geometry = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    area_revision = geometry_revision(
        "AA-R1", "AA", 1, datetime(2026, 1, 1, tzinfo=timezone.utc),
        area_geometry, dataset_id="D-1", minimum=600, maximum=630,
    )
    area = AssessmentArea("AA", "Area", date(2026, 1, 1), [area_revision], area_revision.id)
    r1_geometry = polygon((1, 1), (3, 1), (3, 3), (1, 3))
    event = BlastEvent("BE", "Blast", "production", None, 610)
    event.add_geometry_revision(source_file_name="r1.csv", source_geometry=[],
                                plan_geometry=r1_geometry, elevation=610)
    project_line = SimpleNamespace(points=(PlanPoint(-2, 0), PlanPoint(12, 0)))
    dataset = SimpleNamespace(id="D-1", lines=[project_line])
    state = AssessmentDomainState(blast_events=[event], assessment_areas=[area], datasets=[dataset])
    links = AssessmentEventLinkService(state); links.refresh_suggestions(area)
    return state, links, area, event, area.event_links[0], area_geometry, r1_geometry, project_line


def fake_page(state, links, area, link):
    received = []
    preview = SimpleNamespace(set_comparison_geometry=lambda *args: received.append(args))
    page = SimpleNamespace(
        _selected_link=lambda: link,
        controller=SimpleNamespace(links=links, state=state), area=area,
        link_preview=preview,
    )
    return page, received


def test_inline_preview_uses_area_frozen_event_revision_and_project_lines():
    state, links, area, event, link, area_geometry, r1_geometry, project_line = scenario()
    r1_id = link.geometry_revision_id
    event.add_geometry_revision(source_file_name="r2.csv", source_geometry=[],
                                plan_geometry=polygon((6, 6), (8, 6), (8, 8), (6, 8)), elevation=610)
    page, received = fake_page(state, links, area, link)

    AssessmentAreaPage.refresh_link_preview(page)

    primary, comparison, lines, context = received[0]
    assert primary == area_geometry
    assert comparison == r1_geometry
    assert lines == [project_line]
    assert link.geometry_revision_id == r1_id
    assert all(value in context for value in ("Blast", "production", "610", "suggested", r1_id, "Stale"))


def test_missing_frozen_revision_keeps_area_and_context_without_fallback():
    state, links, area, event, link, area_geometry, _r1_geometry, project_line = scenario()
    current_geometry = event.active_geometry_revision().plan_geometry
    link.geometry_revision_id = "MISSING-R1"
    page, received = fake_page(state, links, area, link)

    AssessmentAreaPage.refresh_link_preview(page)

    primary, comparison, lines, context = received[0]
    assert primary == area_geometry
    assert comparison is None and comparison != current_geometry
    assert lines == [project_line]
    assert "unavailable" in context
    assert "not substituted" in context


def test_no_selection_has_neutral_preview_with_area_context():
    state, links, area, _event, _link, area_geometry, _r1_geometry, project_line = scenario()
    page, received = fake_page(state, links, area, None)

    AssessmentAreaPage.refresh_link_preview(page)

    assert received[0][:3] == (area_geometry, None, [project_line])
    assert received[0][3] == "Select a linked event to preview its geometry."


def test_comparison_widget_renders_both_geometries_and_remains_navigable():
    app = QApplication.instance() or QApplication([])
    _ = app
    area = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    event = polygon((2, 2), (4, 2), (4, 4), (2, 4))
    line = SimpleNamespace(points=(PlanPoint(-1, 0), PlanPoint(11, 0)))
    widget = PlanGeometryWidget()

    widget.set_comparison_geometry(area, event, [line], "comparison")

    assert widget.comparison_geometries == (area, event)
    assert len(widget._project_items) == 1
    assert widget.view.dragMode() == widget.view.DragMode.ScrollHandDrag
    assert widget.context.text() == "comparison"


def test_show_on_plan_navigation_contract_is_removed():
    assert not hasattr(AssessmentAreaPage, "show_link_on_plan")
