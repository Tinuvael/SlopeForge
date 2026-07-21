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


def build_contour_geometry(imported_lines: Sequence[DatamineLine]) -> ContourGeometryResult:
    """Build a plan MultiPoint from the maximum-Z collar of every drillhole line."""
    if not imported_lines:
        raise BlastGeometryError("Contour geometry import contains no drillhole lines")

    collars: list[DataminePoint] = []
    frozen_lines: list[DatamineLine] = []
    for line in imported_lines:
        if not line.points:
            raise BlastGeometryError(f"Drillhole line {line.source_id!r} has no points")
        collar = max(line.points, key=lambda point: point.z)
        collars.append(DataminePoint.from_dict(collar.to_dict()))
        frozen_lines.append(DatamineLine.from_dict(line.to_dict()))

    multipoint = PlanMultiPoint(tuple(PlanPoint(point.x, point.y) for point in collars))
    return ContourGeometryResult(tuple(frozen_lines), tuple(collars), multipoint)
