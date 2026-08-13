from __future__ import annotations

from datetime import date

from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision
from domain.assessment.geometry import AssessmentBoundary, derive_elevation_summary, derive_plan_polygon
from domain.blasting.entities import utc_now


class AssessmentAreaService:
    """Orchestrates immutable boundary revisions; snapping remains pure domain policy."""
    def __init__(self, state: AssessmentDomainState): self.state = state

    @staticmethod
    def _build_revision(area_id: str, number: int, boundary: AssessmentBoundary, change_reason=None):
        polygon = derive_plan_polygon(boundary)
        minimum, maximum = derive_elevation_summary(boundary)
        return AssessmentAreaGeometryRevision(f"{area_id}-R{number:03d}", area_id, number, utc_now(),
                                              boundary, polygon, minimum, maximum, change_reason)

    def create_area(self, *, name: str, assessment_date: date, boundary: AssessmentBoundary) -> AssessmentArea:
        area_id = f"AA-{max([int(a.id.split('-')[-1]) for a in self.state.assessment_areas if a.id.startswith('AA-') and a.id.split('-')[-1].isdigit()] or [0]) + 1:03d}"
        revision = self._build_revision(area_id, 1, boundary)
        area = AssessmentArea(area_id, name.strip() or area_id, assessment_date, [revision], revision.id, [])
        self.state.assessment_areas.append(area)
        return area

    def revise_area(self, area: AssessmentArea, *, boundary: AssessmentBoundary, change_reason=None):
        if area.is_archived: raise ValueError("Restore the Assessment Area before editing it")
        revision = self._build_revision(area.id, max((r.revision_number for r in area.geometry_revisions), default=0)+1,
                                        boundary, change_reason)
        area.geometry_revisions.append(revision); area.active_geometry_revision_id = revision.id
        return revision
