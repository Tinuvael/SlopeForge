from pathlib import Path

import pytest

from prototype_2d.connectivity import build_endpoint_connections
from prototype_2d.csv_importer import detect_columns, import_datamine_csv, sniff_delimiter
from prototype_2d.geometry import extract_segment, nearest_point_on_polyline, project_point_to_segment
from prototype_2d.models import BenchSectionDraft, DatamineLine, DataminePoint, LineSegmentSelection, PrototypeState
from prototype_2d.storage import load_state, save_state

FIXTURE = Path(__file__).parent / "fixtures" / "datamine_lines_sample.csv"


def write_csv(tmp_path, text, name="data.csv", encoding="utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


def test_import_extended_sid_ptn_keeps_equal_ptn_in_separate_lines(tmp_path):
    path = write_csv(tmp_path, "PID,X,Y,Z,SID,PTN,PVALUE,TYPE\n1,0,0,700,100,1,A,CREST\n2,1,0,700,100,2,B,CREST\n3,2,0,700,100,3,C,CREST\n4,0,1,700,200,1,D,CREST\n5,1,1,700,200,2,E,CREST\n6,2,1,700,200,3,F,CREST\n")
    result = import_datamine_csv(path)
    assert [line.source_id for line in result.lines] == ["100", "200"]
    assert [[point.pvalue for point in line.points] for line in result.lines] == [["A", "B", "C"], ["D", "E", "F"]]
    assert result.summary.line_count == 2


def test_import_clean_pid_xyz_sid_without_type_pvalue_ptn(tmp_path):
    path = write_csv(tmp_path, "PID,X,Y,Z,SID\n2,2,0,700,L1\n1,1,0,700,L1\n")
    line = import_datamine_csv(path).lines[0]
    assert line.source_id == "L1"
    assert [p.x for p in line.points] == [1.0, 2.0]
    assert line.source_type is None and line.assigned_type is None
    assert all(p.pvalue is None for p in line.points)


def test_import_legacy_xp_yp_zp_ptn_fallback_line_id(tmp_path):
    path = write_csv(tmp_path, "XP,YP,ZP,PTN\n0,0,700,OLD-A\n1,0,700,OLD-A\n")
    result = import_datamine_csv(path)
    assert result.lines[0].source_id == "OLD-A"
    assert result.lines[0].elevation == 700


@pytest.mark.parametrize("delimiter,text", [(",", "PID,X,Y,Z,SID\n1,0,0,1,A\n"), (";", "PID;X;Y;Z;SID\n1;0;0;1;A\n"), ("\t", "PID\tX\tY\tZ\tSID\n1\t0\t0\t1\tA\n")])
def test_import_delimiters(tmp_path, delimiter, text):
    path = write_csv(tmp_path, text)
    result = import_datamine_csv(path)
    assert result.summary.delimiter == delimiter
    assert len(result.lines) == 1


def test_utf8_bom_and_precision(tmp_path):
    path = write_csv(tmp_path, "PID,X,Y,Z,SID\n1,100.123456789,200.987654321,700.00001,A\n", encoding="utf-8-sig")
    line = import_datamine_csv(path).lines[0]
    assert line.points[0].x == 100.123456789
    assert line.points[0].y == 200.987654321


def test_detect_columns_logical_names():
    mapping = detect_columns(["PID", "X", "Y", "Z", "SID", "PTN", "PVALUE", "TYPE"])
    assert mapping["LINE_ID"] == "SID"
    assert mapping["POINT_ORDER"] == "PTN"
    assert mapping["SOURCE_TYPE"] == "TYPE"


def test_point_order_fallback_to_rows_when_no_point_order(tmp_path):
    path = write_csv(tmp_path, "X,Y,Z,LINE_ID\n2,0,700,A\n1,0,700,A\n")
    line = import_datamine_csv(path).lines[0]
    assert [p.x for p in line.points] == [2.0, 1.0]


def test_sniffer_fallback():
    assert sniff_delimiter("PID,X,Y,Z,SID\n") == ","
    assert sniff_delimiter("", "semicolon") == ";"


def test_import_skips_bad_rows_and_reports(tmp_path):
    path = write_csv(tmp_path, "PID,X,Y,Z,SID\n1,0,0,700,A\n2,bad,0,700,A\n,,,,\n")
    result = import_datamine_csv(path)
    assert result.summary.valid_points == 1
    assert result.summary.failed_rows == 1
    assert result.summary.skipped_rows == 1


def test_elevation_horizontal_tolerance_variable_and_median():
    horizontal = DatamineLine("H", [DataminePoint(0, 0, 700, 1), DataminePoint(1, 0, 700.04, 2), DataminePoint(2, 0, 700.02, 3)])
    variable = DatamineLine("V", [DataminePoint(0, 0, 680, 1), DataminePoint(1, 0, 715, 2)])
    assert horizontal.is_horizontal
    assert horizontal.z_min == 700
    assert horizontal.z_max == 700.04
    assert horizontal.z_median == 700.02
    assert horizontal.elevation == 700.02
    assert not variable.is_horizontal
    assert variable.elevation is None
    assert variable.display_elevation() == "Z=680…715"


def test_projection_nearest_extract_and_reverse_order():
    line = import_datamine_csv(FIXTURE).lines[0]
    projected, t, distance = project_point_to_segment(110.123456789, 205.987654321, line.points[0], line.points[1])
    assert 0 < t < 1
    assert distance > 0
    _nearest, position, nearest_distance = nearest_point_on_polyline(line, 121, 206)
    assert position > 0 and nearest_distance >= 0
    start, end, points = extract_segment(line, 30, 5)
    assert (start, end) == (5, 30)
    assert len(points) >= 2


def test_bench_draft_intermediates_prevent_duplicate():
    draft = BenchSectionDraft("U-001", "S-001", "S-002", ["S-001"])
    draft.add_intermediate("S-003")
    assert draft.intermediate_segment_ids == ["S-001", "S-003"]
    with pytest.raises(ValueError):
        draft.add_intermediate("S-003")


def test_json_round_trip_preserves_coordinates_and_segments(tmp_path):
    line = import_datamine_csv(FIXTURE).lines[0]
    start, end, points = extract_segment(line, 0, 12.5)
    segment = LineSegmentSelection("S-001", line.source_id, start, end, points, "upper_boundary", line.elevation, "test")
    state = PrototypeState(str(FIXTURE), [line], [segment], [BenchSectionDraft("U-001", "S-001", "S-001", ["S-001"])])
    path = tmp_path / "state.json"
    save_state(state, path)
    restored = load_state(path)
    assert restored.lines[0].points[0].x == 100.123456789
    assert restored.segments[0].source_line_ids == [line.source_id]
    assert restored.drafts[0].id == "U-001"


def make_line(line_id, y=0, z=700, line_type="CREST", start_x=0, end_x=10):
    return DatamineLine(line_id, [DataminePoint(start_x, y, z, 1), DataminePoint(end_x, y, z, 2)], None, line_type, line_type)


def test_connectivity_endpoint_in_tolerance_preserves_sid():
    a = make_line("SID-1", end_x=10)
    b = make_line("SID-2", start_x=10.5, end_x=20)
    connections = build_endpoint_connections([a, b], tolerance=1)
    assert len(connections) == 1
    assert {connections[0].from_line_id, connections[0].to_line_id} == {"SID-1", "SID-2"}


def test_connectivity_rejects_outside_tolerance_type_and_horizon():
    a = make_line("A", end_x=10, line_type="CREST", z=700)
    far = make_line("F", start_x=20, end_x=30, line_type="CREST", z=700)
    other_type = make_line("T", start_x=10, line_type="TOE", z=700)
    other_horizon = make_line("Z", start_x=10, line_type="CREST", z=705)
    assert build_endpoint_connections([a, far], tolerance=1) == []
    assert build_endpoint_connections([a, other_type], tolerance=1) == []
    assert build_endpoint_connections([a, other_horizon], tolerance=1) == []


def test_connectivity_middle_intersection_is_not_connection():
    a = make_line("A", y=0, start_x=0, end_x=10)
    b = DatamineLine("B", [DataminePoint(5, -5, 700, 1), DataminePoint(5, 5, 700, 2)], None, "CREST", "CREST")
    assert build_endpoint_connections([a, b], tolerance=1) == []
