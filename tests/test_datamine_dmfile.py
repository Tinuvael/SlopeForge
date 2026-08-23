from pathlib import Path

import pytest

from infrastructure.datamine.dmfile import (
    DMFILE_PROG_ID,
    DatamineReadError,
    DatamineUnavailableError,
    read_datamine_table_preview,
)


class FakeSchema:
    FieldCount = 3
    SpecialValueAbsent = -999.0

    @staticmethod
    def GetFieldName(index: int) -> str:
        return ("XP", "YP", "COLOUR")[index - 1]


class FakeDmTable:
    DefaultDatamineFormat = ".dmx"

    def __init__(self) -> None:
        self.Schema = FakeSchema()
        self.rows = (
            (100.0, 200.0, 3.0),
            (101.0, -999.0, 4.0),
            (102.0, 202.0, 4.0),
        )
        self.row_index = 0
        self.open_args = None

    def Open(self, path: str, mode: int) -> None:
        self.open_args = (path, mode)

    def GetRowCount(self) -> int:
        return len(self.rows)

    def GetColumn(self, index: int):
        return self.rows[self.row_index][index - 1]

    def GetNextRow(self) -> None:
        self.row_index += 1


def test_preview_reads_schema_rows_and_absent_values(tmp_path: Path) -> None:
    source = tmp_path / "sample.dmx"
    source.write_bytes(b"fixture")
    table = FakeDmTable()
    prog_ids = []

    preview = read_datamine_table_preview(
        source,
        row_limit=2,
        dispatch_factory=lambda prog_id: prog_ids.append(prog_id) or table,
    )

    assert prog_ids == [DMFILE_PROG_ID]
    assert table.open_args == (str(source.resolve()), 0)
    assert preview.file_name == "sample.dmx"
    assert preview.default_datamine_format == ".dmx"
    assert preview.fields == ("XP", "YP", "COLOUR")
    assert preview.row_count == 3
    assert preview.rows == ((100.0, 200.0, 3.0), (101.0, None, 4.0))


def test_preview_row_limit_zero_reads_no_rows(tmp_path: Path) -> None:
    source = tmp_path / "sample.dm"
    source.write_bytes(b"fixture")

    preview = read_datamine_table_preview(
        source,
        row_limit=0,
        dispatch_factory=lambda _prog_id: FakeDmTable(),
    )

    assert preview.row_count == 3
    assert preview.rows == ()


def test_preview_rejects_non_datamine_extension_before_dispatch(tmp_path: Path) -> None:
    source = tmp_path / "sample.csv"
    source.write_text("XP,YP", encoding="utf-8")

    with pytest.raises(DatamineReadError, match="Use \\.dm or \\.dmx"):
        read_datamine_table_preview(source, dispatch_factory=lambda _prog_id: FakeDmTable())


def test_preview_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DatamineReadError, match="does not exist"):
        read_datamine_table_preview(
            tmp_path / "missing.dmx",
            dispatch_factory=lambda _prog_id: FakeDmTable(),
        )


def test_preview_wraps_com_creation_failure(tmp_path: Path) -> None:
    source = tmp_path / "sample.dmx"
    source.write_bytes(b"fixture")

    def fail_dispatch(_prog_id: str):
        raise RuntimeError("class not registered")

    with pytest.raises(DatamineUnavailableError, match="DmFile.DmTable"):
        read_datamine_table_preview(source, dispatch_factory=fail_dispatch)
