from pathlib import Path

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
