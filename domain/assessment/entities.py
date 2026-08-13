from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5
from domain.geometry.types import PlanGeometry, PlanPolygon, plan_geometry_from_dict
from domain.assessment.geometry import AssessmentBoundary, derive_elevation_summary, derive_plan_polygon

ELEVATION_STORAGE_TOLERANCE_M = 0.0005 + 1e-12


def _canonical_elevation_summary(boundary, stored_minimum, stored_maximum):
    """Accept NUMERIC(12,3) quantization but keep frozen XYZ as canonical truth."""
    derived = derive_elevation_summary(boundary)
    stored = (stored_minimum, stored_maximum)
    for label, canonical, persisted in zip(("minimum", "maximum"), derived, stored):
        if (canonical is None) != (persisted is None):
            raise ValueError(f"Stored {label} elevation presence disagrees with frozen boundary geometry")
        if canonical is not None and abs(canonical-persisted) > ELEVATION_STORAGE_TOLERANCE_M:
            raise ValueError(f"Stored {label} elevation disagrees with frozen boundary geometry")
    return derived

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None

def _datetime_from_text(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None

LinkStatus = Literal["suggested", "confirmed", "excluded"]
LinkSource = Literal["automatic", "manual"]

@dataclass
class AssessmentEventLink:
    blast_event_id: str
    geometry_revision_id: str
    status: LinkStatus = "suggested"
    source: LinkSource = "automatic"
    frozen_intersection_geometry: PlanGeometry | None = None
    id: str | None = None
    assessment_area_geometry_revision_id: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status not in {"suggested", "confirmed", "excluded"}:
            raise ValueError(f"Unsupported link status: {self.status!r}")
        if self.source not in {"automatic", "manual"}:
            raise ValueError(f"Unsupported link source: {self.source!r}")
        if self.created_at is not None and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "assessment_area_geometry_revision_id": self.assessment_area_geometry_revision_id,
            "blast_event_id": self.blast_event_id,
            "geometry_revision_id": self.geometry_revision_id,
            "status": self.status,
            "source": self.source,
            "created_at": _datetime_to_text(self.created_at),
            "frozen_intersection_geometry": (
                self.frozen_intersection_geometry.to_dict() if self.frozen_intersection_geometry else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, area_revision_id: str | None = None,
                  fallback_created_at: datetime | None = None) -> "AssessmentEventLink":
        geometry_data = data.get("frozen_intersection_geometry")
        revision_id = data.get("assessment_area_geometry_revision_id") or area_revision_id
        link_id = data.get("id") or str(uuid5(
            NAMESPACE_URL,
            "slopeforge-link:" + ":".join((revision_id or "legacy", data["blast_event_id"],
                                           data["geometry_revision_id"], data.get("source", "automatic"))),
        ))
        created_at = _datetime_from_text(data.get("created_at")) or fallback_created_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
        return cls(
            blast_event_id=data["blast_event_id"],
            geometry_revision_id=data["geometry_revision_id"],
            status=data.get("status", "suggested"),
            source=data.get("source", "automatic"),
            frozen_intersection_geometry=plan_geometry_from_dict(geometry_data) if geometry_data else None,
            id=link_id,
            assessment_area_geometry_revision_id=revision_id,
            created_at=created_at,
        )


@dataclass(frozen=True)
class AssessmentAreaGeometryRevision:
    id: str
    assessment_area_id: str
    revision_number: int
    created_at: datetime
    boundary: AssessmentBoundary
    final_geometry_frozen: PlanPolygon
    min_elevation: float | None
    max_elevation: float | None
    change_reason: str | None = None

    def __post_init__(self):
        if self.revision_number < 1: raise ValueError("Geometry revision number must be positive")
        if derive_plan_polygon(self.boundary) != self.final_geometry_frozen:
            raise ValueError("Frozen plan polygon must be derived from the ordered boundary")
        if derive_elevation_summary(self.boundary) != (self.min_elevation, self.max_elevation):
            raise ValueError("Elevation summary must be derived from frozen boundary geometry")

    @property
    def source_dataset_ids(self):
        ids = []
        for segment in self.boundary.segments:
            for anchor in (getattr(segment, "start_anchor", None), getattr(segment, "end_anchor", None)):
                if anchor and anchor.source_dataset_id not in ids: ids.append(anchor.source_dataset_id)
        return tuple(ids)

    def to_dict(self):
        return {"id": self.id, "assessment_area_id": self.assessment_area_id, "revision_number": self.revision_number,
                "created_at": self.created_at.isoformat(), "boundary": self.boundary.to_dict(),
                "final_geometry_frozen": self.final_geometry_frozen.to_dict(), "min_elevation": self.min_elevation,
                "max_elevation": self.max_elevation, "change_reason": self.change_reason}

    @classmethod
    def from_dict(cls, data):
        boundary = AssessmentBoundary.from_dict(data["boundary"])
        final = plan_geometry_from_dict(data["final_geometry_frozen"])
        if not isinstance(final, PlanPolygon): raise ValueError("Assessment Area footprint must be a Polygon")
        stored_minimum = None if data.get("min_elevation") is None else float(data["min_elevation"])
        stored_maximum = None if data.get("max_elevation") is None else float(data["max_elevation"])
        minimum, maximum = _canonical_elevation_summary(boundary, stored_minimum, stored_maximum)
        return cls(data["id"], data["assessment_area_id"], int(data["revision_number"]),
                   datetime.fromisoformat(data["created_at"]), boundary, final,
                   minimum, maximum, data.get("change_reason"))


@dataclass
class AssessmentArea:
    id: str
    name: str
    assessment_date: date
    geometry_revisions: list[AssessmentAreaGeometryRevision] = field(default_factory=list)
    active_geometry_revision_id: str | None = None
    event_links: list[AssessmentEventLink] = field(default_factory=list)
    is_archived: bool = False
    archived_at: datetime | None = None
    archive_reason: str | None = None

    def __post_init__(self):
        if self.geometry_revisions and self.active_geometry_revision_id is None: self.active_geometry_revision_id = self.geometry_revisions[-1].id
        active = next((r for r in self.geometry_revisions if r.id == self.active_geometry_revision_id), None)
        for link in self.event_links:
            link.assessment_area_geometry_revision_id = link.assessment_area_geometry_revision_id or self.active_geometry_revision_id
            link.id = link.id or str(uuid5(NAMESPACE_URL, "slopeforge-link:" + ":".join((link.assessment_area_geometry_revision_id or "legacy", link.blast_event_id, link.geometry_revision_id, link.source))))
            link.created_at = link.created_at or (active.created_at if active else datetime(1970, 1, 1, tzinfo=timezone.utc))

    def active_geometry_revision(self):
        revision = next((r for r in self.geometry_revisions if r.id == self.active_geometry_revision_id), None)
        if revision is None: raise ValueError(f"Assessment Area {self.id!r} has no active geometry revision")
        return revision

    def links_for_revision(self, revision_id=None):
        return [link for link in self.event_links if link.assessment_area_geometry_revision_id == (revision_id or self.active_geometry_revision_id)]

    @property
    def boundary(self): return self.active_geometry_revision().boundary
    @property
    def final_geometry_frozen(self): return self.active_geometry_revision().final_geometry_frozen
    @property
    def min_elevation(self): return self.active_geometry_revision().min_elevation
    @property
    def max_elevation(self): return self.active_geometry_revision().max_elevation

    def archive(self, reason=None, archived_at=None):
        self.is_archived, self.archived_at, self.archive_reason = True, archived_at or utc_now(), reason
    def restore(self):
        self.is_archived, self.archived_at, self.archive_reason = False, None, None

    def to_dict(self):
        return {"id": self.id, "name": self.name, "assessment_date": self.assessment_date.isoformat(),
                "geometry_revisions": [r.to_dict() for r in self.geometry_revisions],
                "active_geometry_revision_id": self.active_geometry_revision_id,
                "event_links": [link.to_dict() for link in self.event_links], "is_archived": self.is_archived,
                "archived_at": _datetime_to_text(self.archived_at), "archive_reason": self.archive_reason}

    @classmethod
    def from_dict(cls, data):
        revisions = [AssessmentAreaGeometryRevision.from_dict(item) for item in data.get("geometry_revisions", [])]
        if not revisions: raise ValueError("Assessment Area requires a canonical boundary geometry revision")
        active_id = data.get("active_geometry_revision_id")
        return cls(data["id"], data["name"], date.fromisoformat(data["assessment_date"]), revisions, active_id,
                   [AssessmentEventLink.from_dict(item, area_revision_id=active_id,
                    fallback_created_at=next((r.created_at for r in revisions if r.id == active_id), revisions[-1].created_at)) for item in data.get("event_links", [])],
                   bool(data.get("is_archived", False)), _datetime_from_text(data.get("archived_at")), data.get("archive_reason"))
