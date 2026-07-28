from datetime import date, datetime, timezone
import json

import pytest

from prototype_2d.assessment_area_service import AssessmentAreaService, AssessmentFragmentCandidate
from prototype_2d.domain import AssessmentDomainState, PlanLineString, PlanPoint, PlanPolygon, ProjectLinesDataset
from prototype_2d.geometry import (clip_datamine_line_by_polygon, point_in_polygon, polygon_area,
                                   polygon_self_intersects, segment_intersection)
from prototype_2d.models import DatamineLine, DataminePoint


def polygon(*coordinates):
    points = tuple(PlanPoint(*item) for item in coordinates)
    return PlanPolygon(points + (points[0],))


def line(source_id, elevation, *coordinates):
    return DatamineLine(source_id, [DataminePoint(x, y, elevation, i) for i, (x, y) in enumerate(coordinates)])


def test_basic_polygon_operations_include_boundary():
    square = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    assert polygon_area(square) == 100
    assert point_in_polygon(PlanPoint(5, 5), square)
    assert point_in_polygon(PlanPoint(0, 5), square)
    assert not point_in_polygon(PlanPoint(15, 5), square)
    assert segment_intersection(PlanPoint(-1, 5), PlanPoint(11, 5), PlanPoint(0, 0), PlanPoint(0, 10)) == PlanPoint(0, 5)


def test_bow_tie_self_intersects():
    assert polygon_self_intersects(polygon((0, 0), (10, 10), (0, 10), (10, 0)))


def test_clipping_inside_outside_and_multiple_concave_fragments():
    concave = polygon((0, 0), (10, 0), (10, 10), (7, 10), (7, 3), (3, 3), (3, 10), (0, 10))
    fragments = clip_datamine_line_by_polygon(line("L", 100, (-2, 5), (12, 5)), concave)
    assert [[(p.x, p.y) for p in item.points] for item in fragments] == [[(0, 5), (3, 5)], [(7, 5), (10, 5)]]
    assert clip_datamine_line_by_polygon(line("outside", 100, (-2, 12), (12, 12)), concave) == []
    inside = clip_datamine_line_by_polygon(line("inside", 100, (1, 1), (9, 1)), concave)
    assert inside == [PlanLineString((PlanPoint(1, 1), PlanPoint(9, 1)))]
    assert clip_datamine_line_by_polygon(line("zero", 100, (1, 1), (1, 1)), concave) == []


def test_service_filters_non_horizontal_assigns_roles_and_freezes_source():
    lines = [line("lower", 100, (-1, 1), (11, 1)), line("middle", 110, (-1, 5), (11, 5)),
             line("upper", 120, (-1, 9), (11, 9))]
    sloping = DatamineLine("slope", [DataminePoint(0, 2, 100, 1), DataminePoint(10, 2, 101, 2)])
    state = AssessmentDomainState(datasets=[ProjectLinesDataset("D-001", "Main", datetime.now(timezone.utc), "a.csv", True, lines + [sloping])])
    service = AssessmentAreaService(state); selection = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    candidates = service.generate_candidates(selection)
    assert [item.source_line_id for item in candidates] == ["lower", "middle", "upper"]
    area = service.create_area(name="Wall", assessment_date=date(2026, 7, 28), selection_polygon=selection, selected_fragments=candidates)
    assert [item.role for item in area.horizon_slices] == ["lower_boundary", "internal_horizon", "upper_boundary"]
    assert area.source_dataset_id == "D-001"
    lines[0].points[0].x = 999
    assert area.horizon_slices[0].frozen_geometry.points[0] == PlanPoint(0, 1)
    state.datasets.append(ProjectLinesDataset("D-002", "New", datetime.now(timezone.utc), "b.csv", True, [])); state.datasets[0].is_active = False
    assert area.source_dataset_id == "D-001"


def test_selection_constraints_and_final_endpoint_orientation():
    fragment = PlanLineString((PlanPoint(0, 0), PlanPoint(10, 0)))
    with pytest.raises(ValueError, match="двух"):
        AssessmentAreaService.validate_selection([AssessmentFragmentCandidate("a", 1, 1, fragment)])
    with pytest.raises(ValueError, match="один"):
        AssessmentAreaService.validate_selection([AssessmentFragmentCandidate("a", 1, 1, fragment), AssessmentFragmentCandidate("b", 1, 1, fragment)])
    final = AssessmentAreaService.build_final_geometry(fragment, PlanLineString((PlanPoint(0, 10), PlanPoint(10, 10))))
    assert final.ring == (PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10), PlanPoint(0, 10), PlanPoint(0, 0))


def test_area_json_round_trip_and_archive_restore():
    dataset = ProjectLinesDataset("D-001", "Main", datetime.now(timezone.utc), "a.csv", True,
                                  [line("lo", 1, (0, 1), (10, 1)), line("hi", 2, (0, 9), (10, 9))])
    state = AssessmentDomainState(datasets=[dataset]); service = AssessmentAreaService(state)
    selection = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    area = service.create_area(name="A", assessment_date=date.today(), selection_polygon=selection,
                               selected_fragments=service.generate_candidates(selection))
    area.archive("done"); restored = AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.assessment_areas[0].to_dict() == area.to_dict()
    restored.assessment_areas[0].restore(); assert not restored.assessment_areas[0].is_archived
