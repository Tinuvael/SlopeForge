from __future__ import annotations

from dataclasses import dataclass, asdict
from math import hypot

from .models import DatamineLine, HORIZONTAL_Z_TOLERANCE

ENDPOINTS = ("start", "end")


@dataclass(frozen=True)
class LineEndpointRef:
    line_id: str
    endpoint: str
    x: float
    y: float
    z: float

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class LineConnection:
    from_line_id: str
    from_endpoint: str
    to_line_id: str
    to_endpoint: str
    distance: float
    connection_type: str = "endpoint_snap"
    auto_generated: bool = True

    def to_dict(self):
        return asdict(self)


def endpoints_for_line(line: DatamineLine) -> list[LineEndpointRef]:
    if not line.points:
        return []
    return [
        LineEndpointRef(line.source_id, "start", line.points[0].x, line.points[0].y, line.points[0].z),
        LineEndpointRef(line.source_id, "end", line.points[-1].x, line.points[-1].y, line.points[-1].z),
    ]


def compatible_types(a: DatamineLine, b: DatamineLine) -> bool:
    return (a.assigned_type or a.source_type) == (b.assigned_type or b.source_type)


def compatible_elevation(a: DatamineLine, b: DatamineLine, z_tolerance: float = HORIZONTAL_Z_TOLERANCE) -> bool:
    if a.is_horizontal and b.is_horizontal:
        return a.elevation is not None and b.elevation is not None and abs(a.elevation - b.elevation) <= z_tolerance
    return not a.is_horizontal and not b.is_horizontal


def build_endpoint_connections(
    lines: list[DatamineLine],
    tolerance: float,
    z_tolerance: float = HORIZONTAL_Z_TOLERANCE,
) -> list[LineConnection]:
    connections: list[LineConnection] = []
    by_id = {line.source_id: line for line in lines}
    endpoint_refs = [endpoint for line in lines for endpoint in endpoints_for_line(line)]
    for index, left in enumerate(endpoint_refs):
        for right in endpoint_refs[index + 1 :]:
            if left.line_id == right.line_id:
                continue
            left_line = by_id[left.line_id]
            right_line = by_id[right.line_id]
            if not compatible_types(left_line, right_line):
                continue
            if not compatible_elevation(left_line, right_line, z_tolerance):
                continue
            distance = hypot(left.x - right.x, left.y - right.y)
            if distance <= tolerance:
                connections.append(LineConnection(left.line_id, left.endpoint, right.line_id, right.endpoint, distance))
    return connections
