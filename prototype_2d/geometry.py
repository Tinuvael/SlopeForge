from __future__ import annotations

from dataclasses import replace
from math import hypot

from .models import DatamineLine, DataminePoint


def _dist(a: DataminePoint, b: DataminePoint) -> float:
    return hypot(b.x - a.x, b.y - a.y)


def line_length(line: DatamineLine) -> float:
    return sum(_dist(a, b) for a, b in zip(line.points, line.points[1:]))


def point_at_position(line: DatamineLine, position: float) -> DataminePoint:
    if not line.points:
        raise ValueError("Line has no points")
    if position <= 0 or len(line.points) == 1:
        return replace(line.points[0])
    remaining = position
    for a, b in zip(line.points, line.points[1:]):
        length = _dist(a, b)
        if remaining <= length:
            t = 0 if length == 0 else remaining / length
            return DataminePoint(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t, a.source_row_number, a.pvalue, dict(a.extra_values))
        remaining -= length
    return replace(line.points[-1])


def project_point_to_segment(px: float, py: float, a: DataminePoint, b: DataminePoint) -> tuple[DataminePoint, float, float]:
    dx, dy = b.x - a.x, b.y - a.y
    denom = dx * dx + dy * dy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, ((px - a.x) * dx + (py - a.y) * dy) / denom))
    projected = DataminePoint(a.x + dx * t, a.y + dy * t, a.z + (b.z - a.z) * t, a.source_row_number, a.pvalue, dict(a.extra_values))
    return projected, t, hypot(px - projected.x, py - projected.y)


def nearest_point_on_polyline(line: DatamineLine, x: float, y: float) -> tuple[DataminePoint, float, float]:
    if len(line.points) < 2:
        p = point_at_position(line, 0)
        return p, 0.0, hypot(x - p.x, y - p.y)
    best = None
    distance_along = 0.0
    travelled = 0.0
    for a, b in zip(line.points, line.points[1:]):
        projected, t, distance = project_point_to_segment(x, y, a, b)
        seg_len = _dist(a, b)
        position = travelled + seg_len * t
        if best is None or distance < best[2]:
            best = (projected, position, distance)
        travelled += seg_len
    return best  # type: ignore[return-value]


def extract_segment(line: DatamineLine, start_position: float, end_position: float) -> tuple[float, float, list[DataminePoint]]:
    start, end = sorted((start_position, end_position))
    total = line_length(line)
    start, end = max(0.0, min(start, total)), max(0.0, min(end, total))
    points = [point_at_position(line, start)]
    travelled = 0.0
    for a, b in zip(line.points, line.points[1:]):
        seg_len = _dist(a, b)
        next_travelled = travelled + seg_len
        if start < next_travelled and travelled < end:
            if start < next_travelled and travelled >= start and next_travelled <= end:
                points.append(replace(b))
        travelled = next_travelled
    end_point = point_at_position(line, end)
    if not points or points[-1].x != end_point.x or points[-1].y != end_point.y:
        points.append(end_point)
    return start, end, points
