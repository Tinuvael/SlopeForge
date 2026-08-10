from __future__ import annotations

from datetime import date

from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision, AssessmentHorizonSlice
from domain.assessment.geometry import AssessmentFragmentCandidate, build_final_geometry, validate_selection
from application.state.assessment_domain_state import AssessmentDomainState
from domain.geometry.types import PlanLineString, PlanPoint, PlanPolygon
from domain.blasting.entities import utc_now
from domain.geometry.operations import clip_datamine_line_by_polygon, validate_simple_polygon


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
        return validate_selection(selected)

    @staticmethod
    def build_final_geometry(lower: PlanLineString, upper: PlanLineString) -> PlanPolygon:
        return build_final_geometry(lower, upper)

    def _build_revision(self, area_id: str, revision_number: int, selection_polygon: PlanPolygon,
                        selected_fragments: list[AssessmentFragmentCandidate], change_reason=None):
        dataset = self.state.active_dataset()
        if dataset is None:
            raise ValueError("Нет активного Dataset")
        validate_simple_polygon(selection_polygon)
        selected = self.validate_selection(selected_fragments)
        slices = []
        for index, candidate in enumerate(selected, 1):
            role = "lower_boundary" if index == 1 else "upper_boundary" if index == len(selected) else "internal_horizon"
            copied = PlanLineString(tuple(PlanPoint(point.x, point.y) for point in candidate.geometry.points))
            slices.append(AssessmentHorizonSlice(f"{area_id}-R{revision_number:03d}-HS-{index:03d}", candidate.source_line_id,
                                                 candidate.elevation, role, copied))
        final = self.build_final_geometry(slices[0].frozen_geometry, slices[-1].frozen_geometry)
        frozen_selection = PlanPolygon(tuple(PlanPoint(point.x, point.y) for point in selection_polygon.ring))
        return AssessmentAreaGeometryRevision(f"{area_id}-R{revision_number:03d}", area_id, revision_number,
            utc_now(), dataset.id, frozen_selection, final, selected[0].elevation, selected[-1].elevation,
            tuple(slices), change_reason)

    def create_area(self, *, name: str, assessment_date: date, selection_polygon: PlanPolygon,
                    selected_fragments: list[AssessmentFragmentCandidate]) -> AssessmentArea:
        area_id = f"AA-{max([int(a.id.split('-')[-1]) for a in self.state.assessment_areas if a.id.startswith('AA-') and a.id.split('-')[-1].isdigit()] or [0]) + 1:03d}"
        revision = self._build_revision(area_id, 1, selection_polygon, selected_fragments)
        area = AssessmentArea(area_id, name.strip() or area_id, assessment_date, [revision], revision.id, [])
        self.state.assessment_areas.append(area)
        return area

    def revise_area(self, area: AssessmentArea, *, selection_polygon: PlanPolygon,
                    selected_fragments: list[AssessmentFragmentCandidate], change_reason=None) -> AssessmentAreaGeometryRevision:
        if area.is_archived:
            raise ValueError("Сначала восстановите Assessment Area из архива")
        number = max((item.revision_number for item in area.geometry_revisions), default=0) + 1
        revision = self._build_revision(area.id, number, selection_polygon, selected_fragments, change_reason)
        area.geometry_revisions.append(revision)
        area.active_geometry_revision_id = revision.id
        return revision
