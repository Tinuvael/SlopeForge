from pathlib import Path

import pytest

from infrastructure.geometry_import.csv import detect_columns, import_datamine_csv, sniff_delimiter
from domain.geometry.types import DatamineLine, DataminePoint

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


def test_csv_closure_requires_explicit_repeated_endpoint(tmp_path):
    from domain.assessment.geometry import project_line_is_closed
    closed=import_datamine_csv(write_csv(tmp_path,
        "PID,X,Y,Z,SID\n1,0,0,100,C\n2,10,0,101,C\n3,10,10,102,C\n4,0,0,100,C\n")).lines[0]
    opened=import_datamine_csv(write_csv(tmp_path,
        "PID,X,Y,Z,SID\n1,0,0,100,O\n2,10,0,101,O\n3,10,10,102,O\n","open.csv")).lines[0]
    assert project_line_is_closed(closed) and not project_line_is_closed(opened)


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
