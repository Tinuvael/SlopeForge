"""XY-only conversion of common imported lines into Domain footprints."""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot
from typing import Sequence

from .domain import PlanPoint, PlanPolygon
from .geometry import validate_simple_polygon
from .models import DatamineLine

DOMAIN_CLOSURE_TOLERANCE_M = 0.05
DOMAIN_MIN_AREA_M2 = 1e-6


class DomainGeometryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DomainPolygonBuildResult:
    polygons: tuple[PlanPolygon, ...]
    skipped_open_lines: int = 0
    skipped_degenerate_lines: int = 0


def build_domain_polygons(
    imported_lines: Sequence[DatamineLine], tolerance: float = DOMAIN_CLOSURE_TOLERANCE_M
) -> DomainPolygonBuildResult:
    polygons: list[PlanPolygon] = []
    open_count = degenerate_count = 0
    for line in imported_lines:
        xy = tuple(PlanPoint(float(point.x), float(point.y)) for point in line.points)
        if len(xy) < 2 or hypot(xy[0].x - xy[-1].x, xy[0].y - xy[-1].y) > tolerance:
            open_count += 1
            continue
        vertices = xy[:-1]
        distinct: list[PlanPoint] = []
        for point in vertices:
            if not any(hypot(point.x-other.x, point.y-other.y) <= tolerance for other in distinct):
                distinct.append(point)
        area = abs(sum(
            vertices[i].x * vertices[(i + 1) % len(vertices)].y
            - vertices[(i + 1) % len(vertices)].x * vertices[i].y
            for i in range(len(vertices))
        )) / 2 if vertices else 0
        if len(distinct) < 3 or area <= DOMAIN_MIN_AREA_M2:
            degenerate_count += 1
            continue
        polygon = PlanPolygon(vertices + (vertices[0],))
        try:
            validate_simple_polygon(polygon)
        except ValueError:
            degenerate_count += 1
            continue
        polygons.append(polygon)
    if not polygons:
        raise DomainGeometryValidationError(
            "No valid closed Domain polygons were found in the geometry file."
        )
    return DomainPolygonBuildResult(tuple(polygons), open_count, degenerate_count)
