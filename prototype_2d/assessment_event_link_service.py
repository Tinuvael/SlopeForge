"""Revision-safe BlastEvent linking for Assessment Areas (no Qt dependencies).

Production matches intentionally store no intersection geometry: this module only
proves polygon intersection and does not attempt polygon clipping.  Contour links
freeze copied matching collar points as a :class:`PlanMultiPoint`.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .domain import (AssessmentArea, AssessmentDomainState, AssessmentEventLink,
                     BlastEvent, PlanMultiPoint, PlanPolygon, utc_now)
from .geometry import (points_from_multipoint_inside_polygon,
                       polygon_intersects_polygon)


@dataclass(frozen=True)
class AssessmentEventLinkCandidate:
    blast_event_id: str
    geometry_revision_id: str
    event_type: str
    elevation_matches: bool
    spatial_matches: bool
    frozen_intersection_geometry: PlanMultiPoint | None = None


@dataclass(frozen=True)
class LinkRefreshResult:
    production_candidates: int
    contour_candidates: int
    suggestions_added: int

    @property
    def total_suggestions(self) -> int:
        return self.suggestions_added


class AssessmentEventLinkService:
    def __init__(self, state: AssessmentDomainState):
        self.state = state

    def evaluate_event(self, area: AssessmentArea, event: BlastEvent) -> AssessmentEventLinkCandidate | None:
        area_revision = area.active_geometry_revision()
        event_revision = event.active_geometry_revision()
        if event.is_archived or event_revision is None:
            return None
        elevation = area_revision.lower_elevation < event.elevation <= area_revision.upper_elevation
        geometry = event_revision.plan_geometry
        matched = None
        spatial = False
        if event.event_type == "production" and isinstance(geometry, PlanPolygon):
            spatial = polygon_intersects_polygon(geometry, area_revision.selection_polygon_frozen)
        elif event.event_type == "contour" and isinstance(geometry, PlanMultiPoint):
            points = points_from_multipoint_inside_polygon(geometry, area_revision.selection_polygon_frozen)
            spatial = bool(points)
            if points:
                matched = PlanMultiPoint(points)
        return AssessmentEventLinkCandidate(event.id, event_revision.id, event.event_type,
                                            elevation, spatial, matched)

    def find_candidates(self, area: AssessmentArea) -> list[AssessmentEventLinkCandidate]:
        return [candidate for event in self.state.blast_events
                if (candidate := self.evaluate_event(area, event)) is not None
                and candidate.elevation_matches and candidate.spatial_matches]

    def refresh_suggestions(self, area: AssessmentArea) -> LinkRefreshResult:
        self._ensure_editable(area)
        revision_id = area.active_geometry_revision_id
        # Only disposable automatic suggestions for this area revision are rebuilt.
        area.event_links[:] = [link for link in area.event_links if not (
            link.assessment_area_geometry_revision_id == revision_id
            and link.source == "automatic" and link.status == "suggested")]
        protected_event_ids = {link.blast_event_id for link in area.links_for_revision()
                               if link.status != "suggested" or link.source == "manual"}
        production = contour = added = 0
        for candidate in self.find_candidates(area):
            if candidate.event_type == "production": production += 1
            else: contour += 1
            if candidate.blast_event_id in protected_event_ids:
                continue
            area.event_links.append(self._new_link(area, candidate.blast_event_id,
                candidate.geometry_revision_id, "suggested", "automatic",
                candidate.frozen_intersection_geometry))
            added += 1
        return LinkRefreshResult(production, contour, added)

    def confirm_link(self, area: AssessmentArea, link_id: str) -> AssessmentEventLink:
        self._ensure_editable(area); link = self._link(area, link_id); link.status = "confirmed"; return link

    def exclude_link(self, area: AssessmentArea, link_id: str) -> AssessmentEventLink:
        self._ensure_editable(area); link = self._link(area, link_id); link.status = "excluded"; return link

    def restore_suggestion(self, area: AssessmentArea, link_id: str) -> AssessmentEventLink:
        self._ensure_editable(area); link = self._link(area, link_id)
        link.status = "suggested" if link.source == "automatic" else "confirmed"
        return link

    def add_manual_link(self, area: AssessmentArea, blast_event_id: str) -> AssessmentEventLink:
        self._ensure_editable(area)
        event = self.event(blast_event_id)
        if event.is_archived or event.active_geometry_revision() is None:
            raise ValueError("Архивное событие или событие без геометрии нельзя связать")
        if any(link.blast_event_id == blast_event_id for link in area.links_for_revision()):
            raise ValueError("Это событие уже связано с активной ревизией Assessment Area")
        candidate = self.evaluate_event(area, event)
        assert candidate is not None
        link = self._new_link(area, event.id, candidate.geometry_revision_id,
                              "confirmed", "manual", candidate.frozen_intersection_geometry)
        area.event_links.append(link)
        return link

    def is_stale(self, link: AssessmentEventLink) -> bool:
        event = next((item for item in self.state.blast_events if item.id == link.blast_event_id), None)
        return event is None or event.active_geometry_revision_id != link.geometry_revision_id

    def event(self, event_id: str) -> BlastEvent:
        event = next((item for item in self.state.blast_events if item.id == event_id), None)
        if event is None: raise ValueError(f"BlastEvent {event_id!r} не найден")
        return event

    @staticmethod
    def linked_revision(event: BlastEvent, link: AssessmentEventLink):
        """Resolve the exact frozen revision, never the event's current revision."""
        return next((revision for revision in event.geometry_revisions
                     if revision.id == link.geometry_revision_id), None)

    def _link(self, area: AssessmentArea, link_id: str) -> AssessmentEventLink:
        link = next((item for item in area.links_for_revision() if item.id == link_id), None)
        if link is None: raise ValueError("Связь активной ревизии не найдена")
        return link

    @staticmethod
    def _ensure_editable(area: AssessmentArea) -> None:
        if area.is_archived: raise ValueError("Связи архивной Assessment Area доступны только для чтения")

    @staticmethod
    def _new_link(area, event_id, geometry_revision_id, status, source, frozen):
        return AssessmentEventLink(event_id, geometry_revision_id, status, source, frozen,
            id=f"AEL-{uuid4()}", assessment_area_geometry_revision_id=area.active_geometry_revision_id,
            created_at=utc_now())
