from pathlib import Path

import pytest

from prototype_2d.csv_importer import import_datamine_csv
from prototype_2d.geometry import extract_segment, nearest_point_on_polyline, project_point_to_segment
from prototype_2d.models import BenchSectionDraft, LineSegmentSelection, PrototypeState
from prototype_2d.storage import load_state, save_state

FIXTURE = Path(__file__).parent / "fixtures" / "datamine_lines_sample.csv"


def test_import_groups_by_ptn_and_preserves_order():
    lines = import_datamine_csv(FIXTURE)
    assert [line.source_id for line in lines] == ["L730-A", "L700-A", "L715-C", "L680-D"]
    assert [p.source_row_number for p in lines[0].points] == [2, 3, 4]
    assert lines[0].points[0].x == 100.123456789


def test_elevations_source_type_and_assigned_type():
    state = PrototypeState(lines=import_datamine_csv(FIXTURE))
    assert state.elevations() == [680.0, 700.0, 715.0, 730.25]
    line = state.lines[0]
    assert line.source_type == "DESIGN"
    line.assigned_type = "USER_CHANGED"
    assert line.source_type == "DESIGN"
    assert line.assigned_type == "USER_CHANGED"


def test_projection_and_nearest_point_on_polyline():
    line = import_datamine_csv(FIXTURE)[0]
    projected, t, distance = project_point_to_segment(110.123456789, 205.987654321, line.points[0], line.points[1])
    assert 0 < t < 1
    assert distance > 0
    nearest, position, nearest_distance = nearest_point_on_polyline(line, 121, 206)
    assert nearest.x == pytest.approx(120.0, abs=2)
    assert position > 0
    assert nearest_distance >= 0


def test_extract_segment_and_reverse_order_normalized():
    line = import_datamine_csv(FIXTURE)[0]
    start, end, points = extract_segment(line, 30, 5)
    assert start == 5
    assert end == 30
    assert len(points) >= 2
    assert points[0].x != points[-1].x


def test_bench_draft_intermediates_prevent_duplicate():
    draft = BenchSectionDraft("U-001", "S-001", "S-002", ["S-001"])
    draft.add_intermediate("S-003")
    assert draft.intermediate_segment_ids == ["S-001", "S-003"]
    with pytest.raises(ValueError):
        draft.add_intermediate("S-003")


def test_json_round_trip_preserves_coordinates_and_segments(tmp_path):
    line = import_datamine_csv(FIXTURE)[0]
    start, end, points = extract_segment(line, 0, 12.5)
    segment = LineSegmentSelection("S-001", line.source_id, start, end, points, "upper_boundary", line.elevation, "test")
    state = PrototypeState(str(FIXTURE), [line], [segment], [BenchSectionDraft("U-001", "S-001", "S-001", ["S-001"])])
    path = tmp_path / "state.json"
    save_state(state, path)
    restored = load_state(path)
    assert restored.lines[0].points[0].x == 100.123456789
    assert restored.segments[0].extracted_points[-1].x == pytest.approx(segment.extracted_points[-1].x)
    assert restored.drafts[0].id == "U-001"
