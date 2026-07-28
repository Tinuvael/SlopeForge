from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import hypot

from .domain import (AssessmentArea, AssessmentDomainState, AssessmentHorizonSlice,
                     PlanLineString, PlanPoint, PlanPolygon)
from .geometry import clip_datamine_line_by_polygon, validate_simple_polygon


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


class AssessmentAreaService:
    def __init__(self, state: AssessmentDomainState):
        self.state = state

    def generate_candidates(self, polygon: PlanPolygon) -> list[AssessmentFragmentCandidate]:
        validate_simple_polygon(polygon)
        dataset = self.state.active_dataset()
        if dataset is None:
            raise ValueError("Сначала загрузите и выберите активный Dataset")
        candidates = []
        for line in dataset.lines:
            if not line.is_horizontal or line.elevation is None:
                continue
            for number, fragment in enumerate(clip_datamine_line_by_polygon(line, polygon), 1):
                candidates.append(AssessmentFragmentCandidate(line.source_id, line.elevation, number, fragment))
        return sorted(candidates, key=lambda item: (item.elevation, item.source_line_id, item.fragment_number))

    @staticmethod
    def validate_selection(selected: list[AssessmentFragmentCandidate]) -> list[AssessmentFragmentCandidate]:
        elevations = [item.elevation for item in selected]
        if len(elevations) != len(set(elevations)):
            raise ValueError("На одной отметке можно выбрать только один фрагмент")
        if len(set(elevations)) < 2:
            raise ValueError("Выберите фрагменты минимум на двух разных отметках")
        return sorted(selected, key=lambda item: item.elevation)

    @staticmethod
    def build_final_geometry(lower: PlanLineString, upper: PlanLineString) -> PlanPolygon:
        lower_points = list(lower.points)
        forward = list(upper.points)
        reversed_points = list(reversed(upper.points))
        cost_forward = hypot(lower_points[-1].x-forward[0].x, lower_points[-1].y-forward[0].y) + hypot(forward[-1].x-lower_points[0].x, forward[-1].y-lower_points[0].y)
        cost_reversed = hypot(lower_points[-1].x-reversed_points[0].x, lower_points[-1].y-reversed_points[0].y) + hypot(reversed_points[-1].x-lower_points[0].x, reversed_points[-1].y-lower_points[0].y)
        chosen = reversed_points if cost_reversed < cost_forward else forward
        ring = tuple(lower_points + chosen + [lower_points[0]])
        polygon = PlanPolygon(ring)
        validate_simple_polygon(polygon)
        return polygon

    def create_area(self, *, name: str, assessment_date: date, selection_polygon: PlanPolygon,
                    selected_fragments: list[AssessmentFragmentCandidate]) -> AssessmentArea:
        dataset = self.state.active_dataset()
        if dataset is None:
            raise ValueError("Нет активного Dataset")
        validate_simple_polygon(selection_polygon)
        selected = self.validate_selection(selected_fragments)
        area_id = f"AA-{max([int(a.id.split('-')[-1]) for a in self.state.assessment_areas if a.id.startswith('AA-') and a.id.split('-')[-1].isdigit()] or [0]) + 1:03d}"
        slices = []
        for index, candidate in enumerate(selected, 1):
            role = "lower_boundary" if index == 1 else "upper_boundary" if index == len(selected) else "internal_horizon"
            copied = PlanLineString(tuple(PlanPoint(point.x, point.y) for point in candidate.geometry.points))
            slices.append(AssessmentHorizonSlice(f"{area_id}-HS-{index:03d}", candidate.source_line_id,
                                                 candidate.elevation, role, copied))
        final = self.build_final_geometry(slices[0].frozen_geometry, slices[-1].frozen_geometry)
        frozen_selection = PlanPolygon(tuple(PlanPoint(point.x, point.y) for point in selection_polygon.ring))
        area = AssessmentArea(area_id, name.strip() or area_id, assessment_date, dataset.id,
                              frozen_selection, final, selected[0].elevation, selected[-1].elevation, slices, [])
        self.state.assessment_areas.append(area)
        return area
