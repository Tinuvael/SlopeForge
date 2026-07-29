from __future__ import annotations

from dataclasses import replace
from math import hypot

from .models import DatamineLine, DataminePoint
from .domain import PlanLineString, PlanMultiPoint, PlanPoint, PlanPolygon

GEOMETRY_TOLERANCE = 1e-9


def polygon_area(polygon: PlanPolygon) -> float:
    """Signed shoelace area (absolute value), in plan-coordinate units squared."""
    return abs(sum(a.x * b.y - b.x * a.y for a, b in zip(polygon.ring, polygon.ring[1:]))) / 2


def _cross(a: PlanPoint, b: PlanPoint, c: PlanPoint) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _on_segment(point: PlanPoint, a: PlanPoint, b: PlanPoint, tolerance: float) -> bool:
    return (abs(_cross(a, b, point)) <= tolerance and
            min(a.x, b.x) - tolerance <= point.x <= max(a.x, b.x) + tolerance and
            min(a.y, b.y) - tolerance <= point.y <= max(a.y, b.y) + tolerance)


def segment_intersection(a: PlanPoint, b: PlanPoint, c: PlanPoint, d: PlanPoint,
                         tolerance: float = GEOMETRY_TOLERANCE) -> PlanPoint | None:
    """Return the unique segment intersection; for overlap, the first shared endpoint."""
    rx, ry, sx, sy = b.x - a.x, b.y - a.y, d.x - c.x, d.y - c.y
    denominator = rx * sy - ry * sx
    qx, qy = c.x - a.x, c.y - a.y
    if abs(denominator) <= tolerance:
        if abs(qx * ry - qy * rx) > tolerance:
            return None
        for point in (a, b, c, d):
            if _on_segment(point, a, b, tolerance) and _on_segment(point, c, d, tolerance):
                return point
        return None
    t = (qx * sy - qy * sx) / denominator
    u = (qx * ry - qy * rx) / denominator
    if -tolerance <= t <= 1 + tolerance and -tolerance <= u <= 1 + tolerance:
        return PlanPoint(a.x + max(0.0, min(1.0, t)) * rx, a.y + max(0.0, min(1.0, t)) * ry)
    return None


def point_in_polygon(point: PlanPoint, polygon: PlanPolygon,
                     tolerance: float = GEOMETRY_TOLERANCE) -> bool:
    """Ray casting with the polygon boundary explicitly considered inside."""
    inside = False
    for a, b in zip(polygon.ring, polygon.ring[1:]):
        if _on_segment(point, a, b, tolerance):
            return True
        if (a.y > point.y) != (b.y > point.y):
            crossing_x = a.x + (point.y - a.y) * (b.x - a.x) / (b.y - a.y)
            if crossing_x >= point.x - tolerance:
                inside = not inside
    return inside


def polygon_intersection_evidence(first: PlanPolygon, second: PlanPolygon,
                                  tolerance: float = GEOMETRY_TOLERANCE) -> tuple[PlanPoint, ...]:
    """Return deterministic copied witness points, not a fabricated clipped polygon."""
    evidence: list[PlanPoint] = []
    for a, b in zip(first.ring, first.ring[1:]):
        for c, d in zip(second.ring, second.ring[1:]):
            point = segment_intersection(a, b, c, d, tolerance)
            if point is not None:
                evidence.append(PlanPoint(point.x, point.y))
    evidence.extend(PlanPoint(p.x, p.y) for p in first.ring[:-1] if point_in_polygon(p, second, tolerance))
    evidence.extend(PlanPoint(p.x, p.y) for p in second.ring[:-1] if point_in_polygon(p, first, tolerance))
    unique: list[PlanPoint] = []
    for point in evidence:
        if not any(hypot(point.x-other.x, point.y-other.y) <= tolerance for other in unique):
            unique.append(point)
    return tuple(sorted(unique, key=lambda p: (p.x, p.y)))


def polygon_intersects_polygon(first: PlanPolygon, second: PlanPolygon,
                               tolerance: float = GEOMETRY_TOLERANCE) -> bool:
    """Simple-polygon intersection including containment and boundary contact."""
    return bool(polygon_intersection_evidence(first, second, tolerance))


def points_from_multipoint_inside_polygon(multipoint: PlanMultiPoint, polygon: PlanPolygon,
                                          tolerance: float = GEOMETRY_TOLERANCE) -> tuple[PlanPoint, ...]:
    """Copy collars inside or on the selection boundary."""
    return tuple(PlanPoint(point.x, point.y) for point in multipoint.points
                 if point_in_polygon(point, polygon, tolerance))


def polygon_self_intersects(polygon: PlanPolygon, tolerance: float = GEOMETRY_TOLERANCE) -> bool:
    edges = list(zip(polygon.ring, polygon.ring[1:]))
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if segment_intersection(a, b, *edges[j], tolerance) is not None:
                return True
    return False


def validate_simple_polygon(polygon: PlanPolygon, tolerance: float = GEOMETRY_TOLERANCE) -> None:
    vertices = polygon.ring[:-1]
    if len({(point.x, point.y) for point in vertices}) < 3:
        raise ValueError("Полигон должен содержать минимум три различные вершины")
    if any(hypot(b.x - a.x, b.y - a.y) <= tolerance for a, b in zip(polygon.ring, polygon.ring[1:])):
        raise ValueError("Соседние вершины полигона совпадают")
    if polygon_area(polygon) <= tolerance:
        raise ValueError("Площадь полигона равна нулю")
    if polygon_self_intersects(polygon, tolerance):
        raise ValueError("Границы полигона пересекают сами себя")


def _plan_points(line: DatamineLine | PlanLineString) -> tuple[PlanPoint, ...]:
    if isinstance(line, PlanLineString):
        return line.points
    return tuple(PlanPoint(point.x, point.y) for point in line.points)


def clip_datamine_line_by_polygon(line: DatamineLine | PlanLineString, polygon: PlanPolygon,
                                  tolerance: float = GEOMETRY_TOLERANCE) -> list[PlanLineString]:
    """Clip a polyline against a simple polygon without Qt or external geometry libraries."""
    result: list[PlanLineString] = []
    current: list[PlanPoint] = []
    points = _plan_points(line)
    for start, end in zip(points, points[1:]):
        dx, dy = end.x - start.x, end.y - start.y
        length_sq = dx * dx + dy * dy
        if length_sq <= tolerance * tolerance:
            continue
        cuts = [0.0, 1.0]
        for edge_start, edge_end in zip(polygon.ring, polygon.ring[1:]):
            intersection = segment_intersection(start, end, edge_start, edge_end, tolerance)
            if intersection is not None:
                cuts.append(((intersection.x - start.x) * dx + (intersection.y - start.y) * dy) / length_sq)
        cuts = sorted(max(0.0, min(1.0, value)) for value in cuts)
        unique = [cuts[0]]
        for value in cuts[1:]:
            if abs(value - unique[-1]) > tolerance:
                unique.append(value)
        kept_any = False
        for first, second in zip(unique, unique[1:]):
            if second - first <= tolerance:
                continue
            midpoint = PlanPoint(start.x + dx * (first + second) / 2, start.y + dy * (first + second) / 2)
            if not point_in_polygon(midpoint, polygon, tolerance):
                if current:
                    result.append(PlanLineString(tuple(current))); current = []
                continue
            a = PlanPoint(start.x + dx * first, start.y + dy * first)
            b = PlanPoint(start.x + dx * second, start.y + dy * second)
            if not current or hypot(current[-1].x - a.x, current[-1].y - a.y) > tolerance:
                if current:
                    result.append(PlanLineString(tuple(current)))
                current = [a]
            if hypot(current[-1].x - b.x, current[-1].y - b.y) > tolerance:
                current.append(b)
            kept_any = True
        if not kept_any and current:
            result.append(PlanLineString(tuple(current))); current = []
    if current:
        result.append(PlanLineString(tuple(current)))
    return [fragment for fragment in result if sum(hypot(b.x-a.x, b.y-a.y)
            for a, b in zip(fragment.points, fragment.points[1:])) > tolerance]


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
