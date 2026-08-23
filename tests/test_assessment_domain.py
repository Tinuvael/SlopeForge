from datetime import date, datetime, timezone
import json

import pytest

from domain.geometry.blast import BlastGeometryError, build_contour_geometry, build_production_geometry
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.blasting.entities import BlastEvent
from domain.assessment.entities import AssessmentArea, AssessmentEventLink
from tests.assessment_boundary_fixtures import geometry_revision
from domain.project.project_lines import ProjectLinesDataset
from application.state.assessment_domain_state import AssessmentDomainState
from domain.geometry.types import DatamineLine, DataminePoint
from infrastructure.geometry_import.lines import import_line_geometry
from tests.geometry_test_files import write_dxf_lines


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
    assert result.selected_source_line_id == "upper"
    assert result.representative_elevation == 620
    assert result.maximum_elevation == 620


def test_production_multiple_closed_polygons_reports_clear_import_warning():
    result = build_production_geometry([square(610, source_id="block-1"), square(620, source_id="block-2")])
    assert result.closed_polygon_count == 2
    assert result.multiple_polygons_warning == (
        "Geometry file contains 2 production polygons. One BlastEvent currently supports one polygon. "
        "Import the blocks as separate BlastEvents."
    )
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
        source_file_name="v1.dxf",
        source_geometry=[first_result.source_line],
        plan_geometry=first_result.plan_geometry,
        elevation=first_result.elevation,
        imported_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    second_result = build_production_geometry([square(621, source_id="v2")])
    revision_2 = event.add_geometry_revision(
        source_file_name="v2.dxf",
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
    first = ProjectLinesDataset("D-001", "First", datetime.now(timezone.utc), "first.dxf", False, [])
    second = ProjectLinesDataset("D-002", "Second", datetime.now(timezone.utc), "second.dxf", False, [])
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
        source_file_name="block.dxf",
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


def test_domain_state_round_trip_includes_assessment_area_boundary():
    ring = PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10), PlanPoint(0, 0)))
    revision = geometry_revision("AA-001-R001", "AA-001", 1,
        datetime(2026, 7, 21, tzinfo=timezone.utc), ring, dataset_id="D-001",
        minimum=600, maximum=620)
    area = AssessmentArea("AA-001", "Area 600-620", date(2026, 7, 21), [revision], revision.id,
        [AssessmentEventLink("BE-001", "BE-001-R001", "confirmed", "automatic")])
    state = AssessmentDomainState(assessment_areas=[area])
    restored = AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.to_dict() == state.to_dict()


def test_supported_format_contour_filters_flat_marker_strings(tmp_path):
    source = write_dxf_lines(
        tmp_path / "contour.dxf",
        [
            ("DH-1", [(0, 0, 620), (0.2, 0.2, 630.5), (0.4, 0.4, 610)]),
            ("MARKER-1", [(0, 1, 625), (1, 1, 625)]),
            ("DH-2", [(2, 0, 615), (2.2, 0.2, 630.3), (2.4, 0.4, 605)]),
            ("MARKER-2", [(2, 1, 624.8), (3, 1, 624.8)]),
            ("DH-3", [(4, 0, 612), (4.2, 0.2, 630.4), (4.4, 0.4, 602)]),
            ("MARKER-3", [(4, 1, 624.9), (5, 1, 624.9)]),
        ],
    )
    imported = import_line_geometry(source)
    assert imported.summary.line_count == 6

    result = build_contour_geometry(imported.lines)
    assert result.imported_line_count == 6
    assert result.accepted_drillhole_count == 3
    assert result.ignored_flat_line_count == 3
    assert len(result.plan_geometry.points) == 3
    assert [point.z for point in result.collar_points] == [630.5, 630.3, 630.4]
    assert all(point.z > 624.7 for point in result.collar_points)


def test_contour_equal_maximum_uses_earliest_source_row():
    drillhole = DatamineLine("7", [
        point(1, 1, 630, row=9), point(2, 2, 620, row=10), point(3, 3, 630, row=4)
    ])
    result = build_contour_geometry([drillhole])
    assert result.collar_points[0].source_row_number == 4
    assert result.plan_geometry.points == (PlanPoint(3, 3),)


def test_supported_production_fixture_keeps_highest_closed_line(tmp_path):
    source = write_dxf_lines(
        tmp_path / "production.dxf",
        [
            ("LOWER", [(0,0,620),(10,0,620),(10,10,620),(0,10,620),(0,0,620)]),
            ("UPPER", [(0,0,630),(10,0,630),(10,10,630),(0,10,630),(0,0,630)]),
        ],
    )
    imported = import_line_geometry(source)
    result = build_production_geometry(imported.lines)
    assert imported.summary.line_count == 2
    assert result.elevation == 630
    assert len(result.plan_geometry.ring) == 5


def test_contour_entity_order_selects_same_collars(tmp_path):
    lines = [
        ("DH-A", [(0,0,610),(1,1,630),(2,2,600)]),
        ("DH-B", [(10,0,605),(11,1,625),(12,2,590)]),
        ("MARKER", [(20,0,620),(21,0,620)]),
    ]
    first = import_line_geometry(write_dxf_lines(tmp_path / "first.dxf", lines))
    second = import_line_geometry(write_dxf_lines(tmp_path / "second.dxf", reversed(lines)))
    first_result = build_contour_geometry(first.lines)
    second_result = build_contour_geometry(second.lines)
    collars = lambda result: sorted((collar.x, collar.y, collar.z) for collar in result.collar_points)
    assert collars(first_result) == collars(second_result)
    assert first_result.accepted_drillhole_count == len(first_result.collar_points)
    assert second_result.accepted_drillhole_count == len(second_result.collar_points)
