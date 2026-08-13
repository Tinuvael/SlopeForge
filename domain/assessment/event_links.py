"""Pure matching policy for revision-scoped Assessment/Blast Event links."""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Literal

from domain.assessment.entities import AssessmentArea
from domain.blasting.entities import BlastEvent
from domain.geometry.operations import points_from_multipoint_inside_polygon, polygon_intersects_polygon
from domain.geometry.types import PlanMultiPoint, PlanPolygon


@dataclass(frozen=True)
class AssessmentEventLinkCandidate:
    blast_event_id: str
    geometry_revision_id: str
    event_type: str
    elevation_matches: bool
    spatial_matches: bool
    frozen_intersection_geometry: PlanMultiPoint | None = None
    reason: Literal["matched", "archived", "no_active_geometry", "elevation_outside", "spatial_outside"] = "matched"


def evaluate_event(area: AssessmentArea, event: BlastEvent) -> AssessmentEventLinkCandidate:
    area_revision = area.active_geometry_revision()
    event_revision = event.active_geometry_revision()
    if event.is_archived:
        return AssessmentEventLinkCandidate(event.id, event.active_geometry_revision_id or "", event.event_type,
                                            False, False, reason="archived")
    if event_revision is None:
        return AssessmentEventLinkCandidate(event.id, "", event.event_type, False, False,
                                            reason="no_active_geometry")
    minimum, maximum = area_revision.min_elevation, area_revision.max_elevation
    if minimum is None or maximum is None:
        elevation = False
    elif isclose(minimum, maximum, abs_tol=1e-8):
        elevation = isclose(event.elevation, minimum, abs_tol=1e-8)
    else:
        elevation = minimum < event.elevation <= maximum
    geometry = event_revision.plan_geometry
    matched = None
    spatial = False
    if event.event_type == "production" and isinstance(geometry, PlanPolygon):
        spatial = polygon_intersects_polygon(geometry, area_revision.final_geometry_frozen)
    elif event.event_type == "contour" and isinstance(geometry, PlanMultiPoint):
        points = points_from_multipoint_inside_polygon(geometry, area_revision.final_geometry_frozen)
        spatial = bool(points)
        if points:
            matched = PlanMultiPoint(points)
    reason = "elevation_outside" if not elevation else "matched" if spatial else "spatial_outside"
    return AssessmentEventLinkCandidate(event.id, event_revision.id, event.event_type,
                                        elevation, spatial, matched, reason)
