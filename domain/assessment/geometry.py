"""Pure, immutable Assessment boundary geometry and Project-Line tracing."""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Any, TypeAlias

from domain.geometry.operations import validate_simple_polygon
from domain.geometry.types import DatamineLine, PlanPoint, PlanPolygon

EPSILON = 1e-8


@dataclass(frozen=True)
class SpatialPoint:
    x: float
    y: float
    z: float | None = None

    def __post_init__(self):
        if not isfinite(self.x) or not isfinite(self.y) or (self.z is not None and not isfinite(self.z)):
            raise ValueError("Boundary coordinates must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, value):
        return cls(float(value["x"]), float(value["y"]), None if value.get("z") is None else float(value["z"]))


@dataclass(frozen=True)
class ProjectLineAnchor:
    source_dataset_id: str
    source_line_id: str
    source_segment_index: int
    interpolation_fraction: float
    frozen_point_xyz: SpatialPoint

    def __post_init__(self):
        if not self.source_dataset_id.strip() or not self.source_line_id.strip():
            raise ValueError("Project Line anchor source IDs must be non-empty")
        if self.source_segment_index < 0 or not 0 <= self.interpolation_fraction <= 1:
            raise ValueError("Invalid Project Line anchor position")

    def to_dict(self):
        return {"source_dataset_id": self.source_dataset_id, "source_line_id": self.source_line_id,
                "source_segment_index": self.source_segment_index,
                "interpolation_fraction": self.interpolation_fraction,
                "frozen_point_xyz": self.frozen_point_xyz.to_dict()}

    @classmethod
    def from_dict(cls, value):
        return cls(value["source_dataset_id"], value["source_line_id"], int(value["source_segment_index"]),
                   float(value["interpolation_fraction"]), SpatialPoint.from_dict(value["frozen_point_xyz"]))


@dataclass(frozen=True)
class ProjectLineSpan:
    start_anchor: ProjectLineAnchor
    end_anchor: ProjectLineAnchor
    frozen_trace_xyz: tuple[SpatialPoint, ...]

    def __post_init__(self):
        if (self.start_anchor.source_dataset_id, self.start_anchor.source_line_id) != (self.end_anchor.source_dataset_id, self.end_anchor.source_line_id):
            raise ValueError("A traced span must stay on one Project Line")
        if len(self.frozen_trace_xyz) < 2:
            raise ValueError("A traced span needs at least two points")
        if self.frozen_trace_xyz[0] != self.start_anchor.frozen_point_xyz:
            raise ValueError("Traced span start must match its frozen anchor")
        if self.frozen_trace_xyz[-1] != self.end_anchor.frozen_point_xyz:
            raise ValueError("Traced span end must match its frozen anchor")

    def to_dict(self):
        return {"type": "project_line_span", "start_anchor": self.start_anchor.to_dict(),
                "end_anchor": self.end_anchor.to_dict(), "frozen_trace_xyz": [p.to_dict() for p in self.frozen_trace_xyz]}


@dataclass(frozen=True)
class StraightConnector:
    start_point: SpatialPoint
    end_point: SpatialPoint
    start_anchor: ProjectLineAnchor | None = None
    end_anchor: ProjectLineAnchor | None = None

    def __post_init__(self):
        if hypot(self.end_point.x-self.start_point.x, self.end_point.y-self.start_point.y) <= EPSILON:
            raise ValueError("Straight connector must have non-zero plan length")
        if self.start_anchor and self.start_anchor.frozen_point_xyz != self.start_point:
            raise ValueError("Connector start does not match its frozen anchor")
        if self.end_anchor and self.end_anchor.frozen_point_xyz != self.end_point:
            raise ValueError("Connector end does not match its frozen anchor")

    def to_dict(self):
        return {"type": "straight_connector", "start_point": self.start_point.to_dict(),
                "end_point": self.end_point.to_dict(),
                "start_anchor": self.start_anchor.to_dict() if self.start_anchor else None,
                "end_anchor": self.end_anchor.to_dict() if self.end_anchor else None}


BoundarySegment: TypeAlias = ProjectLineSpan | StraightConnector


def segment_from_dict(value: dict[str, Any]) -> BoundarySegment:
    if value["type"] == "project_line_span":
        return ProjectLineSpan(ProjectLineAnchor.from_dict(value["start_anchor"]),
                               ProjectLineAnchor.from_dict(value["end_anchor"]),
                               tuple(SpatialPoint.from_dict(p) for p in value["frozen_trace_xyz"]))
    if value["type"] == "straight_connector":
        return StraightConnector(SpatialPoint.from_dict(value["start_point"]), SpatialPoint.from_dict(value["end_point"]),
                                 ProjectLineAnchor.from_dict(value["start_anchor"]) if value.get("start_anchor") else None,
                                 ProjectLineAnchor.from_dict(value["end_anchor"]) if value.get("end_anchor") else None)
    raise ValueError("Unsupported Assessment boundary segment")


@dataclass(frozen=True)
class AssessmentBoundary:
    segments: tuple[BoundarySegment, ...]

    def __post_init__(self):
        if len(self.segments) < 3:
            raise ValueError("Assessment boundary requires at least three segments")
        validate_boundary_continuity(self)
        derive_plan_polygon(self)

    def to_dict(self):
        return {"version": 1, "segments": [s.to_dict() for s in self.segments]}

    @classmethod
    def from_dict(cls, value):
        if value.get("version") != 1:
            raise ValueError(f"Unsupported Assessment boundary schema version: {value.get('version')!r}")
        return cls(tuple(segment_from_dict(s) for s in value["segments"]))


@dataclass(frozen=True)
class SnapResult:
    anchor: ProjectLineAnchor
    distance: float
    import_order: int


def interpolate_anchor(dataset_id: str, line: DatamineLine, segment_index: int, fraction: float) -> ProjectLineAnchor:
    if not 0 <= segment_index < len(line.points) - 1 or not 0 <= fraction <= 1:
        raise ValueError("Anchor lies outside the source Project Line")
    a, b = line.points[segment_index], line.points[segment_index + 1]
    point = SpatialPoint(a.x + (b.x-a.x)*fraction, a.y + (b.y-a.y)*fraction, a.z + (b.z-a.z)*fraction)
    return ProjectLineAnchor(dataset_id, line.source_id, segment_index, fraction, point)


def snap_to_project_lines(point: PlanPoint, dataset_id: str, lines: list[DatamineLine], tolerance: float) -> SnapResult | None:
    candidates = []
    for line in lines:
        for index, (a, b) in enumerate(zip(line.points, line.points[1:])):
            dx, dy = b.x-a.x, b.y-a.y
            fraction = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((point.x-a.x)*dx+(point.y-a.y)*dy)/(dx*dx+dy*dy)))
            anchor = interpolate_anchor(dataset_id, line, index, fraction)
            distance = hypot(point.x-anchor.frozen_point_xyz.x, point.y-anchor.frozen_point_xyz.y)
            if distance <= tolerance:
                candidates.append((distance, line.import_order, line.source_id, index, SnapResult(anchor, distance, line.import_order)))
    return min(candidates, key=lambda item: item[:4])[-1] if candidates else None


def extract_project_line_span(line: DatamineLine, start: ProjectLineAnchor, end: ProjectLineAnchor) -> ProjectLineSpan:
    if start.source_line_id != line.source_id or end.source_line_id != line.source_id or start.source_dataset_id != end.source_dataset_id:
        raise ValueError("Anchors do not belong to this Project Line")
    forward = (start.source_segment_index, start.interpolation_fraction) <= (end.source_segment_index, end.interpolation_fraction)
    first, last = (start, end) if forward else (end, start)
    points = [first.frozen_point_xyz]
    points.extend(SpatialPoint(p.x, p.y, p.z) for p in line.points[first.source_segment_index + 1:last.source_segment_index + 1])
    points.append(last.frozen_point_xyz)
    normalized = [p for i, p in enumerate(points) if i == 0 or p != points[i-1]]
    if not forward: normalized.reverse()
    return ProjectLineSpan(start, end, tuple(normalized))


def _segment_points(segment: BoundarySegment) -> tuple[SpatialPoint, ...]:
    return segment.frozen_trace_xyz if isinstance(segment, ProjectLineSpan) else (segment.start_point, segment.end_point)


def validate_boundary_continuity(boundary: AssessmentBoundary, tolerance: float = EPSILON) -> None:
    for current, following in zip(boundary.segments, boundary.segments[1:] + boundary.segments[:1]):
        a, b = _segment_points(current)[-1], _segment_points(following)[0]
        if hypot(a.x-b.x, a.y-b.y) > tolerance:
            raise ValueError("Assessment boundary segments are not continuous")


def derive_plan_polygon(boundary: AssessmentBoundary) -> PlanPolygon:
    points: list[PlanPoint] = []
    for segment in boundary.segments:
        for value in _segment_points(segment):
            point = PlanPoint(value.x, value.y)
            if not points or point != points[-1]: points.append(point)
    if points[-1] != points[0]: points.append(points[0])
    polygon = PlanPolygon(tuple(points))
    validate_simple_polygon(polygon)
    return polygon


def derive_elevation_summary(boundary: AssessmentBoundary) -> tuple[float | None, float | None]:
    values: list[float] = []
    for segment in boundary.segments:
        if isinstance(segment, ProjectLineSpan):
            values.extend(p.z for p in segment.frozen_trace_xyz if p.z is not None)
        else:
            if segment.start_anchor and segment.start_point.z is not None: values.append(segment.start_point.z)
            if segment.end_anchor and segment.end_point.z is not None: values.append(segment.end_point.z)
    return (min(values), max(values)) if values else (None, None)
