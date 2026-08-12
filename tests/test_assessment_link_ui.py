from datetime import date, datetime, timezone

import pytest

try:
    from ui.pages.assessment_area_page import AssessmentAreaPage
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

from application.services.assessment_event_links import AssessmentEventLinkService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision
from domain.blasting.entities import BlastEvent
from domain.geometry.types import PlanPoint, PlanPolygon


def polygon(*coordinates):
    points = tuple(PlanPoint(*xy) for xy in coordinates)
    return PlanPolygon(points + (points[0],))


def scenario():
    area_geometry = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    area_revision = AssessmentAreaGeometryRevision(
        "AA-R1", "AA", 1, datetime(2026, 1, 1, tzinfo=timezone.utc), "D-1",
        area_geometry, area_geometry, 600, 630, (),
    )
    area = AssessmentArea("AA", "Area", date(2026, 1, 1), [area_revision], area_revision.id)
    r1_geometry = polygon((1, 1), (3, 1), (3, 3), (1, 3))
    event = BlastEvent("BE", "Blast", "production", None, 610)
    event.add_geometry_revision(source_file_name="r1.csv", source_geometry=[],
                                plan_geometry=r1_geometry, elevation=610)
    state = AssessmentDomainState(blast_events=[event], assessment_areas=[area])
    links = AssessmentEventLinkService(state); links.refresh_suggestions(area)
    return state, links, area, event, area.event_links[0], r1_geometry


def fake_page(state, links, area, link, received):
    page = type("FakePage", (), {})()
    page._selected_link = lambda: link
    page.controller = type("Controller", (), {"links": links, "state": state})()
    page.area = area
    page.plan = type("Plan", (), {
        "set_geometry": lambda self, geometry, lines, caption: received.append(geometry),
    })()
    page.tabs = type("Tabs", (), {"setCurrentIndex": lambda self, index: None})()
    return page


def test_show_link_on_plan_uses_frozen_revision_not_active_revision():
    state, links, area, event, link, r1_geometry = scenario()
    r1_id = link.geometry_revision_id
    event.add_geometry_revision(source_file_name="r2.csv", source_geometry=[],
                                plan_geometry=polygon((6, 6), (8, 6), (8, 8), (6, 8)),
                                elevation=610)
    assert links.is_stale(link)
    received = []

    AssessmentAreaPage.show_link_on_plan(fake_page(state, links, area, link, received))

    assert received == [r1_geometry]
    assert link.geometry_revision_id == r1_id


def test_show_link_on_plan_reports_missing_frozen_revision_without_fallback(monkeypatch):
    state, links, area, _event, link, _r1_geometry = scenario()
    link.geometry_revision_id = "MISSING-R1"
    warnings = []; received = []
    monkeypatch.setattr("ui.pages.assessment_area_page.QMessageBox.warning",
                        lambda *args: warnings.append(args))

    AssessmentAreaPage.show_link_on_plan(fake_page(state, links, area, link, received))

    assert received == []
    assert len(warnings) == 1
    assert "exact BlastEvent geometry revision" in warnings[0][2]
    assert "not substituted" in warnings[0][2]
