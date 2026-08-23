from pathlib import Path

import pytest

from infrastructure.datamine.strings import DatamineStringImportError, import_datamine_strings


class FakeSchema:
    FieldCount = 8
    SpecialValueAbsent = -999.0

    @staticmethod
    def GetFieldName(index: int) -> str:
        return (
            "XP",
            "YP",
            "ZP",
            "PTN",
            "PVALUE",
            "LSTYLE",
            "SYMBOL",
            "COLOUR",
        )[index - 1]


class FakeStringTable:
    DefaultDatamineFormat = None

    def __init__(self, rows) -> None:
        self.Schema = FakeSchema()
        self.rows = tuple(rows)
        self.row_index = 0

    def Open(self, _path: str, _mode: int) -> None:
        self.row_index = 0

    def GetRowCount(self) -> int:
        return len(self.rows)

    def GetColumn(self, index: int):
        return self.rows[self.row_index][index - 1]

    def GetNextRow(self) -> None:
        self.row_index += 1


def _source_file(tmp_path: Path) -> Path:
    source = tmp_path / "test_strings.dmx"
    source.write_bytes(b"fixture")
    return source


def test_verified_pvalue_ptn_schema_groups_and_orders_lines(tmp_path: Path) -> None:
    source = _source_file(tmp_path)
    rows = (
        # Deliberately not PTN-sorted inside PVALUE=1 to prove ordering.
        (88.0, 68.0, 90.0, 2.0, 1.0, 1001.0, 201.0, 1.0),
        (84.0, 62.0, 90.0, 1.0, 1.0, 1001.0, 201.0, 1.0),
        (87.0, 74.0, 90.0, 3.0, 1.0, 1001.0, 201.0, 1.0),
        (84.0, 62.0, 100.0, 1.0, 2.0, 1001.0, 201.0, 2.0),
        (88.0, 68.0, 100.0, 2.0, 2.0, 1001.0, 201.0, 2.0),
    )

    result = import_datamine_strings(
        source,
        dispatch_factory=lambda _prog_id: FakeStringTable(rows),
    )

    assert result.summary.line_id_field == "PVALUE"
    assert result.summary.point_order_field == "PTN"
    assert result.summary.line_count == 2
    assert result.summary.total_rows == 5
    assert result.summary.colours == (1.0, 2.0)

    first, second = result.lines
    assert first.source_id == "1"
    assert [point.source_row_number for point in first.points] == [2, 1, 3]
    assert [point.pvalue for point in first.points] == ["1", "1", "1"]
    assert first.source_attributes["PVALUE"] == 1.0
    assert first.source_attributes["COLOUR"] == 1.0
    assert first.source_attributes["LSTYLE"] == 1001.0
    assert first.source_attributes["SYMBOL"] == 201.0
    assert first.source_attributes["datamine_line_id_field"] == "PVALUE"
    assert first.source_attributes["datamine_point_order_field"] == "PTN"
    assert first.source_type is None
    assert first.assigned_type is None

    assert second.source_id == "2"
    assert [point.z for point in second.points] == [100.0, 100.0]
    assert second.source_attributes["COLOUR"] == 2.0


def test_sid_is_preferred_when_explicit_sid_exists(tmp_path: Path) -> None:
    source = _source_file(tmp_path)

    class SidSchema(FakeSchema):
        FieldCount = 9

        @staticmethod
        def GetFieldName(index: int) -> str:
            return (
                "XP", "YP", "ZP", "PTN", "PVALUE", "LSTYLE", "SYMBOL", "COLOUR", "SID"
            )[index - 1]

    class SidTable(FakeStringTable):
        def __init__(self) -> None:
            self.Schema = SidSchema()
            self.rows = (
                (0.0, 0.0, 0.0, 1.0, 77.0, 1001.0, 201.0, 3.0, 10.0),
                (1.0, 0.0, 0.0, 2.0, 77.0, 1001.0, 201.0, 3.0, 10.0),
            )
            self.row_index = 0

    result = import_datamine_strings(source, dispatch_factory=lambda _prog_id: SidTable())

    assert result.summary.line_id_field == "SID"
    assert result.lines[0].source_id == "10"
    assert result.lines[0].points[0].pvalue == "77"


def test_duplicate_ptn_within_one_line_is_rejected(tmp_path: Path) -> None:
    source = _source_file(tmp_path)
    rows = (
        (0.0, 0.0, 0.0, 1.0, 1.0, 1001.0, 201.0, 1.0),
        (1.0, 0.0, 0.0, 1.0, 1.0, 1001.0, 201.0, 1.0),
    )

    with pytest.raises(DatamineStringImportError, match="Duplicate PTN"):
        import_datamine_strings(source, dispatch_factory=lambda _prog_id: FakeStringTable(rows))


def test_missing_pvalue_and_sid_fails_with_actionable_schema_error(tmp_path: Path) -> None:
    source = _source_file(tmp_path)

    class MissingIdSchema:
        FieldCount = 4
        SpecialValueAbsent = -999.0

        @staticmethod
        def GetFieldName(index: int) -> str:
            return ("XP", "YP", "ZP", "PTN")[index - 1]

    class MissingIdTable(FakeStringTable):
        def __init__(self) -> None:
            self.Schema = MissingIdSchema()
            self.rows = ((0.0, 0.0, 0.0, 1.0),)
            self.row_index = 0

    with pytest.raises(DatamineStringImportError, match="SID/PVALUE"):
        import_datamine_strings(source, dispatch_factory=lambda _prog_id: MissingIdTable())
