from pathlib import Path

import pytest

from infrastructure.geometry_import import lines as line_imports


def test_dispatches_dmx_to_datamine_string_adapter(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "strings.dmx"
    source.write_bytes(b"fixture")
    sentinel = object()
    calls = []

    def fake_import(path):
        calls.append(Path(path))
        return sentinel

    monkeypatch.setattr(line_imports, "import_datamine_strings", fake_import)

    assert line_imports.import_line_geometry(source) is sentinel
    assert calls == [source]


def test_dispatches_legacy_dm_to_datamine_string_adapter(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "strings.dm"
    source.write_bytes(b"fixture")
    sentinel = object()

    monkeypatch.setattr(line_imports, "import_datamine_strings", lambda path: sentinel)

    assert line_imports.import_line_geometry(source) is sentinel


def test_csv_is_not_a_user_facing_line_geometry_format(tmp_path: Path) -> None:
    source = tmp_path / "strings.csv"
    source.write_text("XP,YP,ZP", encoding="utf-8")

    with pytest.raises(line_imports.LineGeometryImportError, match="Use \\.dxf, \\.dm or \\.dmx"):
        line_imports.import_line_geometry(source)
