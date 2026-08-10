"""Pure geometry policy for Assessment Area candidate selection."""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from domain.geometry.operations import validate_simple_polygon
from domain.geometry.types import PlanLineString, PlanPolygon


@dataclass(frozen=True)
class AssessmentFragmentCandidate:
    source_line_id: str
    elevation: float
    fragment_number: int
    geometry: PlanLineString

    @property
    def id(self) -> str:
        return f"{self.source_line_id}:{self.fragment_number}"

    @property
    def length(self) -> float:
        return sum(hypot(b.x-a.x, b.y-a.y) for a, b in zip(self.geometry.points, self.geometry.points[1:]))


def validate_selection(selected: list[AssessmentFragmentCandidate]) -> list[AssessmentFragmentCandidate]:
    elevations = [item.elevation for item in selected]
    if len(elevations) != len(set(elevations)):
        raise ValueError("На одной отметке можно выбрать только один фрагмент")
    if len(set(elevations)) < 2:
        raise ValueError("Выберите фрагменты минимум на двух разных отметках")
    return sorted(selected, key=lambda item: item.elevation)


def build_final_geometry(lower: PlanLineString, upper: PlanLineString) -> PlanPolygon:
    lower_points = list(lower.points)
    forward = list(upper.points)
    reversed_points = list(reversed(upper.points))
    cost_forward = hypot(lower_points[-1].x-forward[0].x, lower_points[-1].y-forward[0].y) + hypot(forward[-1].x-lower_points[0].x, forward[-1].y-lower_points[0].y)
    cost_reversed = hypot(lower_points[-1].x-reversed_points[0].x, lower_points[-1].y-reversed_points[0].y) + hypot(reversed_points[-1].x-lower_points[0].x, reversed_points[-1].y-lower_points[0].y)
    chosen = reversed_points if cost_reversed < cost_forward else forward
    combined = lower_points + chosen
    normalized = []
    for point in combined:
        if not normalized or point != normalized[-1]:
            normalized.append(point)
    while len(normalized) > 1 and normalized[-1] == normalized[0]:
        normalized.pop()
    polygon = PlanPolygon(tuple(normalized + [normalized[0]]))
    validate_simple_polygon(polygon)
    return polygon
