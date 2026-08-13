"""Pure matching policy for revision-scoped Assessment/Blast Event links."""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isclose
from typing import Literal

from domain.assessment.entities import AssessmentArea
from domain.blasting.entities import BlastEvent
from domain.geometry.operations import point_in_polygon, polygon_intersects_polygon
from domain.geometry.types import PlanMultiPoint, PlanPoint, PlanPolygon

# Assessment elevation projections are stored at millimetre precision.  This
# tolerance only absorbs normal NUMERIC(12,3)/source floating-point noise.
ELEVATION_COMPARISON_TOLERANCE_M = 0.0005 + 1e-12

# Independently imported survey collars may sit centimetres either side of the
# traced line.  This tolerance is only for Contour-to-Assessment link matching.
CONTOUR_LINK_BOUNDARY_TOLERANCE_M = 0.10


def _point_to_segment_distance(point, start, end) -> float:
    dx, dy = end.x-start.x, end.y-start.y
    if dx == 0 and dy == 0:
        return hypot(point.x-start.x, point.y-start.y)
    fraction = max(0.0, min(1.0,
        ((point.x-start.x)*dx+(point.y-start.y)*dy)/(dx*dx+dy*dy)))
    return hypot(point.x-(start.x+fraction*dx), point.y-(start.y+fraction*dy))


def contour_collars_matching_area(multipoint: PlanMultiPoint, polygon: PlanPolygon,
                                  tolerance: float = CONTOUR_LINK_BOUNDARY_TOLERANCE_M
                                  ) -> tuple[PlanPoint, ...]:
    """Copy actual collars inside, on, or conservatively near the boundary."""
    accepted=[]
    for point in multipoint.points:
        near = any(_point_to_segment_distance(point,start,end) <= tolerance
                   for start,end in zip(polygon.ring,polygon.ring[1:]))
        if point_in_polygon(point,polygon) or near:
            accepted.append(PlanPoint(point.x,point.y))
    return tuple(accepted)


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
    elif isclose(minimum, maximum, rel_tol=0.0, abs_tol=ELEVATION_COMPARISON_TOLERANCE_M):
        elevation = isclose(event.elevation, minimum, rel_tol=0.0,
                            abs_tol=ELEVATION_COMPARISON_TOLERANCE_M)
    else:
        above_lower = (event.elevation > minimum and not isclose(
            event.elevation,minimum,rel_tol=0.0,abs_tol=ELEVATION_COMPARISON_TOLERANCE_M))
        at_or_below_upper = (event.elevation <= maximum or isclose(
            event.elevation,maximum,rel_tol=0.0,abs_tol=ELEVATION_COMPARISON_TOLERANCE_M))
        elevation = above_lower and at_or_below_upper
    geometry = event_revision.plan_geometry
    matched = None
    spatial = False
    if event.event_type == "production" and isinstance(geometry, PlanPolygon):
        spatial = polygon_intersects_polygon(geometry, area_revision.final_geometry_frozen)
    elif event.event_type == "contour" and isinstance(geometry, PlanMultiPoint):
        points = contour_collars_matching_area(geometry, area_revision.final_geometry_frozen)
        spatial = bool(points)
        if points:
            matched = PlanMultiPoint(points)
    reason = "elevation_outside" if not elevation else "matched" if spatial else "spatial_outside"
    return AssessmentEventLinkCandidate(event.id, event_revision.id, event.event_type,
                                        elevation, spatial, matched, reason)
