from __future__ import annotations

from typing import Iterable

from domain.blasting.drillholes import Drillhole


def point_in_polygon(x: float, y: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    """Boundary-inclusive even/odd test for a simple XY selection polygon."""
    if len(polygon) < 3:
        return False
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        dx, dy = xj - xi, yj - yi
        cross = (x - xi) * dy - (y - yi) * dx
        if abs(cross) <= 1e-9:
            dot = (x - xi) * dx + (y - yi) * dy
            if -1e-9 <= dot <= dx * dx + dy * dy + 1e-9:
                return True
        crosses = (yi > y) != (yj > y)
        if crosses:
            intersection_x = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x <= intersection_x + 1e-12:
                inside = not inside
        j = i
    return inside


def hole_ids_in_polygon(
    holes: Iterable[Drillhole],
    polygon: Iterable[tuple[float, float]],
) -> set[str]:
    boundary = tuple((float(x), float(y)) for x, y in polygon)
    return {
        hole.hole_id
        for hole in holes
        if point_in_polygon(hole.collar.x, hole.collar.y, boundary)
    }
