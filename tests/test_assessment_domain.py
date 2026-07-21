from datetime import date, datetime, timezone
import json

import pytest

from prototype_2d.blast_geometry import BlastGeometryError, build_contour_geometry, build_production_geometry
from prototype_2d.domain import (
    AssessmentArea,
    AssessmentDomainState,
    AssessmentEventLink,
    AssessmentHorizonSlice,
    BlastEvent,
    PlanLineString,
    PlanPoint,
    PlanPolygon,
    ProjectLinesDataset,
)
from prototype_2d.models import DatamineLine, DataminePoint


def point(x, y, z, row=1):
    return DataminePoint(x, y, z, row)


def line(source_id, coords, order=0):
    return DatamineLine(source_id, [point(*xyz, row=i + 1) for i, xyz in enumerate(coords)], import_order=order)


def square(z, gap=0.0, source_id="square"):
    return line(source_id, [(0, 0, z), (10, 0, z), (10, 10, z), (0, 10, z), (gap, 0, z)])


def test_production_uses_highest_closed_line_only():
    lower = square(600, source_id="lower")
    upper = square(620, source_id="upper")
    result = build_production_geometry([lower, upper])
    assert result.source_line.source_id == "upper"
    assert result.elevation == 620
    assert result.plan_geometry.ring[0] == result.plan_geometry.ring[-1]
    assert len(result.plan_geometry.ring) == 5


def test_production_rejects_open_top_line():
    with pytest.raises(BlastGeometryError, match="not closed"):
        build_production_geometry([square(620, gap=1.0)], closure_tolerance=0.05)


def test_production_closure_tolerance_normalizes_last_point():
    result = build_production_geometry([square(620, gap=0.02)], closure_tolerance=0.05)
    assert result.plan_geometry.ring[-1] == PlanPoint(0, 0)


def test_contour_uses_maximum_z_regardless_of_point_order():
    first = line("dh-1", [(0, 0, 610), (0.5, 0.5, 620), (1, 1, 600)])
    second = line("dh-2", [(2, 2, 605), (3, 3, 615), (2.5, 2.5, 625)])
    result = build_contour_geometry([first, second])
    assert [collar.z for collar in result.collar_points] == [620, 625]
    assert [(p.x, p.y) for p in result.plan_geometry.points] == [(0.5, 0.5), (2.5, 2.5)]


def test_contour_empty_import_is_rejected():
    with pytest.raises(BlastGeometryError, match="no drillhole"):
        build_contour_geometry([])


def test_reimport_creates_new_active_revision_without_mutating_old():
    event = BlastEvent("BE-001", "Block 620", "production", date(2026, 7, 21), 620)
    first_result = build_production_geometry([square(620, source_id="v1")])
    revision_1 = event.add_geometry_revision(
        source_file_name="v1.csv",
        source_geometry=[first_result.source_line],
        plan_geometry=first_result.plan_geometry,
        elevation=first_result.elevation,
        imported_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    second_result = build_production_geometry([square(621, source_id="v2")])
    revision_2 = event.add_geometry_revision(
        source_file_name="v2.csv",
        source_geometry=[second_result.source_line],
        plan_geometry=second_result.plan_geometry,
        elevation=second_result.elevation,
        imported_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )
    assert revision_1.revision_number == 1 and not revision_1.is_active
    assert revision_2.revision_number == 2 and revision_2.is_active
    assert event.active_geometry_revision_id == revision_2.id
    assert revision_1.source_geometry[0].source_id == "v1"


def test_new_dataset_deactivates_previous_and_keeps_history():
    state = AssessmentDomainState()
    first = ProjectLinesDataset("D-001", "First", datetime.now(timezone.utc), "first.csv", False, [])
    second = ProjectLinesDataset("D-002", "Second", datetime.now(timezone.utc), "second.csv", False, [])
    state.add_dataset(first)
    state.add_dataset(second)
    assert len(state.datasets) == 2
    assert not first.is_active
    assert second.is_active
    assert state.active_dataset() is second


def test_archive_filters_active_blast_events_without_deleting_revisions():
    state = AssessmentDomainState()
    event = BlastEvent("BE-001", "Block", "production", None, 620)
    result = build_production_geometry([square(620)])
    event.add_geometry_revision(
        source_file_name="block.csv",
        source_geometry=[result.source_line],
        plan_geometry=result.plan_geometry,
        elevation=result.elevation,
    )
    state.blast_events.append(event)
    event.archive("duplicate")
    assert state.active_blast_events() == []
    assert len(event.geometry_revisions) == 1
    event.restore()
    assert state.active_blast_events() == [event]


def test_domain_state_round_trip_includes_assessment_area_stub():
    ring = PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10), PlanPoint(0, 0)))
    slice_geometry = PlanLineString((PlanPoint(0, 0), PlanPoint(10, 0)))
    area = AssessmentArea(
        id="AA-001",
        name="Area 600-620",
        assessment_date=date(2026, 7, 21),
        source_dataset_id="D-001",
        selection_polygon_frozen=ring,
        final_geometry_frozen=ring,
        lower_elevation=600,
        upper_elevation=620,
        horizon_slices=[AssessmentHorizonSlice("HS-001", "L-600", 600, "lower_boundary", slice_geometry)],
        event_links=[AssessmentEventLink("BE-001", "BE-001-R001", "confirmed", "automatic")],
    )
    state = AssessmentDomainState(assessment_areas=[area])
    restored = AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.to_dict() == state.to_dict()
