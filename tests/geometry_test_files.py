from __future__ import annotations

from pathlib import Path
from typing import Iterable

from domain.geometry.types import DatamineLine, DataminePoint


def test_line(source_id: str, coordinates: Iterable[tuple[float, float, float]], *, order: int = 0) -> DatamineLine:
    """Build a canonical in-memory line for tests that are not testing file import."""
    return DatamineLine(
        source_id,
        [
            DataminePoint(float(x), float(y), float(z), index)
            for index, (x, y, z) in enumerate(coordinates, start=1)
        ],
        import_order=order,
    )


def write_dxf_lines(
    path: str | Path,
    lines: Iterable[tuple[str, Iterable[tuple[float, float, float]]]],
) -> Path:
    """Write straight 3D POLYLINE entities using a currently supported product format."""
    import ezdxf

    target = Path(path)
    if target.suffix.lower() != ".dxf":
        target = target.with_suffix(".dxf")
    document = ezdxf.new("R2010")
    modelspace = document.modelspace()
    for layer, coordinates in lines:
        points = [tuple(map(float, point)) for point in coordinates]
        if not points:
            continue
        if layer not in document.layers:
            document.layers.add(layer)
        modelspace.add_polyline3d(points, dxfattribs={"layer": layer})
    document.saveas(target)
    return target


def write_production_dxf(
    path: str | Path,
    *,
    elevation: float,
    ring: Iterable[tuple[float, float]] = ((1, 1), (4, 1), (4, 4), (1, 1)),
    layer: str = "production",
) -> Path:
    return write_dxf_lines(
        path,
        [(layer, [(x, y, elevation) for x, y in ring])],
    )


def write_contour_dxf(
    path: str | Path,
    drillholes: Iterable[tuple[str, Iterable[tuple[float, float, float]]]],
) -> Path:
    return write_dxf_lines(path, drillholes)
