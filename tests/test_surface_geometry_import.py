from pathlib import Path

import pytest

from infrastructure.datamine.wireframes import (
    DatamineWireframeImportError,
    import_datamine_wireframe,
    resolve_wireframe_pair,
)
from infrastructure.geometry_import.surfaces import import_dxf_surface, import_surface_geometry


class FakeSchema:
    SpecialValueAbsent = -999.0

    def __init__(self, fields):
        self.fields = tuple(fields)
        self.FieldCount = len(self.fields)

    def GetFieldName(self, index: int) -> str:
        return self.fields[index - 1]


class FakeWireframeTable:
    DefaultDatamineFormat = None

    def __init__(self):
        self.rows = ()
        self.row_index = 0
        self.Schema = FakeSchema(())

    def Open(self, path: str, _mode: int) -> None:
        self.row_index = 0
        if Path(path).stem.lower().endswith("pt"):
            self.Schema = FakeSchema(("XP", "YP", "ZP", "PID"))
            self.rows = (
                (0.0, 0.0, 0.0, 1.0),
                (10.0, 0.0, 0.0, 2.0),
                (0.0, 10.0, 0.0, 3.0),
                (10.0, 10.0, 0.0, 4.0),
            )
        else:
            self.Schema = FakeSchema(
                ("PID1", "PID2", "PID3", "TRIANGLE", "COLOUR", "LINK", "LSTYLE", "SYMBOL")
            )
            self.rows = (
                (1.0, 2.0, 3.0, 101.0, 2.0, 0.0, 1001.0, 201.0),
                (2.0, 4.0, 3.0, 102.0, 7.0, 0.0, 1001.0, 201.0),
            )

    def GetRowCount(self) -> int:
        return len(self.rows)

    def GetColumn(self, index: int):
        return self.rows[self.row_index][index - 1]

    def GetNextRow(self) -> None:
        self.row_index += 1


def _wireframe_pair(tmp_path: Path) -> tuple[Path, Path]:
    triangle = tmp_path / "walltr.dmx"
    points = tmp_path / "wallpt.dmx"
    triangle.write_bytes(b"triangles")
    points.write_bytes(b"points")
    return triangle, points


def test_datamine_wireframe_pair_builds_canonical_surface_and_preserves_triangle_attributes(tmp_path: Path) -> None:
    triangle, points = _wireframe_pair(tmp_path)
    assert resolve_wireframe_pair(points) == (triangle, points)

    result = import_datamine_wireframe(
        triangle,
        dispatch_factory=lambda _prog_id: FakeWireframeTable(),
    )

    assert result.triangle_path == triangle
    assert result.point_path == points
    assert len(result.surface.vertices) == 4
    assert len(result.surface.triangles) == 2
    assert result.surface.triangles[0].vertex_indices == (0, 1, 2)
    assert result.surface.triangles[0].source_id == "101"
    assert result.surface.triangles[0].source_attributes["COLOUR"] == 2.0
    assert result.surface.triangles[1].source_attributes["COLOUR"] == 7.0
    assert result.surface.source_files == ("walltr.dmx", "wallpt.dmx")


def test_datamine_wireframe_requires_unambiguous_tr_pt_pair(tmp_path: Path) -> None:
    triangle = tmp_path / "walltr.dmx"
    triangle.write_bytes(b"triangles")
    with pytest.raises(DatamineWireframeImportError, match="matching Datamine \*pt"):
        resolve_wireframe_pair(triangle)


def test_surface_dispatcher_accepts_datamine_pair(tmp_path: Path) -> None:
    triangle, _points = _wireframe_pair(tmp_path)
    result = import_surface_geometry(
        triangle,
        dispatch_factory=lambda _prog_id: FakeWireframeTable(),
    )
    assert result.source_format == "datamine"
    assert result.triangle_count == 2
    assert result.vertex_count == 4
    assert tuple(path.name for path in result.source_paths) == ("walltr.dmx", "wallpt.dmx")


def test_dxf_3dface_surface_preserves_bylayer_effective_colour(tmp_path: Path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "surface.dxf"
    document = ezdxf.new()
    document.layers.add("FACE", color=3)
    document.modelspace().add_3dface(
        [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
        dxfattribs={"layer": "FACE", "color": 256},
    )
    document.saveas(path)

    result = import_dxf_surface(path)

    assert result.source_format == "dxf"
    assert result.vertex_count == 4
    assert result.triangle_count == 2
    assert result.surface.triangles[0].source_attributes["dxf_layer"] == "FACE"
    assert result.surface.triangles[0].source_attributes["dxf_colour_mode"] == "BYLAYER"
    assert result.surface.triangles[0].source_attributes["dxf_effective_aci"] == 3
