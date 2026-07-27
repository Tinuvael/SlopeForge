from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Sequence

from .domain import PlanMultiPoint, PlanPoint, PlanPolygon
from .models import DatamineLine, DataminePoint


class BlastGeometryError(ValueError):
    """Raised when imported Datamine geometry cannot form a BlastEvent geometry."""


@dataclass(frozen=True)
class ProductionGeometryResult:
    source_line: DatamineLine
    plan_geometry: PlanPolygon
    elevation: float


@dataclass(frozen=True)
class ContourGeometryResult:
    source_lines: tuple[DatamineLine, ...]
    collar_points: tuple[DataminePoint, ...]
    plan_geometry: PlanMultiPoint
    imported_line_count: int
    accepted_drillhole_count: int
    ignored_flat_line_count: int


def _line_max_z(line: DatamineLine) -> float:
    if not line.points:
        raise BlastGeometryError(f"Line {line.source_id!r} has no points")
    return max(point.z for point in line.points)


def _endpoint_distance(first: DataminePoint, last: DataminePoint) -> float:
    return sqrt((first.x - last.x) ** 2 + (first.y - last.y) ** 2 + (first.z - last.z) ** 2)


def build_production_geometry(
    imported_lines: Sequence[DatamineLine],
    closure_tolerance: float = 0.05,
) -> ProductionGeometryResult:
    """Build a plan polygon from the closed imported line with the highest maximum Z."""
    if not imported_lines:
        raise BlastGeometryError("Production geometry import contains no lines")
    if closure_tolerance < 0:
        raise ValueError("closure_tolerance must be non-negative")

    indexed_lines = list(enumerate(imported_lines))
    _, selected = max(indexed_lines, key=lambda item: (_line_max_z(item[1]), -item[0]))
    if len(selected.points) < 4:
        raise BlastGeometryError(
            f"Top line {selected.source_id!r} must contain at least three vertices and a closing point"
        )

    first, last = selected.points[0], selected.points[-1]
    distance = _endpoint_distance(first, last)
    if distance > closure_tolerance:
        raise BlastGeometryError(
            f"Top line {selected.source_id!r} is not closed: endpoint gap {distance:.3f} m "
            f"exceeds tolerance {closure_tolerance:.3f} m"
        )

    ring = [PlanPoint(point.x, point.y) for point in selected.points]
    ring[-1] = ring[0]
    polygon = PlanPolygon(tuple(ring))
    return ProductionGeometryResult(selected, polygon, _line_max_z(selected))


def build_contour_geometry(
    imported_lines: Sequence[DatamineLine], vertical_tolerance: float = 1e-6
) -> ContourGeometryResult:
    """Build collars from non-flat Datamine strings that represent drillholes."""
    if not imported_lines:
        raise BlastGeometryError("Contour geometry import contains no drillhole lines")
    if vertical_tolerance < 0:
        raise ValueError("vertical_tolerance must be non-negative")

    collars: list[DataminePoint] = []
    frozen_lines: list[DatamineLine] = []
    ignored_flat_line_count = 0
    for line in imported_lines:
        if len(line.points) < 2:
            continue
        vertical_extent = max(point.z for point in line.points) - min(point.z for point in line.points)
        if vertical_extent <= vertical_tolerance:
            ignored_flat_line_count += 1
            continue
        # Point order can differ from file order. For equal maxima the first
        # physical CSV row wins, so repeated imports stay deterministic.
        collar = min(line.points, key=lambda point: (-point.z, point.source_row_number))
        collars.append(DataminePoint.from_dict(collar.to_dict()))
        frozen_lines.append(DatamineLine.from_dict(line.to_dict()))

    if not collars:
        raise BlastGeometryError("Contour geometry import contains no valid drillhole collars")
    multipoint = PlanMultiPoint(tuple(PlanPoint(point.x, point.y) for point in collars))
    accepted_count = len(frozen_lines)
    assert accepted_count == len(collars) == len(multipoint.points)
    return ContourGeometryResult(
        tuple(frozen_lines), tuple(collars), multipoint, len(imported_lines),
        accepted_count, ignored_flat_line_count,
    )
