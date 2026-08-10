from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5
from domain.geometry.types import PlanGeometry, PlanLineString, PlanPolygon, plan_geometry_from_dict

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None

def _datetime_from_text(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None

HorizonSliceRole = Literal["lower_boundary", "internal_horizon", "upper_boundary"]
LinkStatus = Literal["suggested", "confirmed", "excluded"]
LinkSource = Literal["automatic", "manual"]

@dataclass(frozen=True)
class AssessmentHorizonSlice:
    id: str
    source_line_id: str
    elevation: float
    role: HorizonSliceRole
    frozen_geometry: PlanLineString

    def __post_init__(self) -> None:
        if self.role not in {"lower_boundary", "internal_horizon", "upper_boundary"}:
            raise ValueError(f"Unsupported horizon slice role: {self.role!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_line_id": self.source_line_id,
            "elevation": self.elevation,
            "role": self.role,
            "frozen_geometry": self.frozen_geometry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentHorizonSlice":
        geometry = plan_geometry_from_dict(data["frozen_geometry"])
        if not isinstance(geometry, PlanLineString):
            raise ValueError("AssessmentHorizonSlice geometry must be a LineString")
        return cls(data["id"], data["source_line_id"], float(data["elevation"]), data["role"], geometry)


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
    source_dataset_id: str
    selection_polygon_frozen: PlanPolygon
    final_geometry_frozen: PlanPolygon
    lower_elevation: float
    upper_elevation: float
    horizon_slices: tuple[AssessmentHorizonSlice, ...]
    change_reason: str | None = None

    def __post_init__(self) -> None:
        if self.revision_number < 1:
            raise ValueError("Geometry revision number must be positive")
        if self.lower_elevation >= self.upper_elevation:
            raise ValueError("AssessmentArea lower_elevation must be below upper_elevation")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "assessment_area_id": self.assessment_area_id,
            "revision_number": self.revision_number, "created_at": self.created_at.isoformat(),
            "source_dataset_id": self.source_dataset_id,
            "selection_polygon_frozen": self.selection_polygon_frozen.to_dict(),
            "final_geometry_frozen": self.final_geometry_frozen.to_dict(),
            "lower_elevation": self.lower_elevation, "upper_elevation": self.upper_elevation,
            "horizon_slices": [item.to_dict() for item in self.horizon_slices],
            "change_reason": self.change_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentAreaGeometryRevision":
        selection = plan_geometry_from_dict(data["selection_polygon_frozen"])
        final = plan_geometry_from_dict(data["final_geometry_frozen"])
        if not isinstance(selection, PlanPolygon) or not isinstance(final, PlanPolygon):
            raise ValueError("AssessmentArea frozen geometries must be Polygons")
        return cls(data["id"], data["assessment_area_id"], int(data["revision_number"]),
                   datetime.fromisoformat(data["created_at"]), data["source_dataset_id"], selection, final,
                   float(data["lower_elevation"]), float(data["upper_elevation"]),
                   tuple(AssessmentHorizonSlice.from_dict(item) for item in data.get("horizon_slices", [])),
                   data.get("change_reason"))


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

    def __post_init__(self) -> None:
        if self.geometry_revisions and self.active_geometry_revision_id is None:
            self.active_geometry_revision_id = self.geometry_revisions[-1].id
        active = next((r for r in self.geometry_revisions if r.id == self.active_geometry_revision_id), None)
        for link in self.event_links:
            link.assessment_area_geometry_revision_id = link.assessment_area_geometry_revision_id or self.active_geometry_revision_id
            link.id = link.id or str(uuid5(NAMESPACE_URL, "slopeforge-link:" + ":".join((
                link.assessment_area_geometry_revision_id or "legacy", link.blast_event_id,
                link.geometry_revision_id, link.source))))
            link.created_at = link.created_at or (active.created_at if active else datetime(1970, 1, 1, tzinfo=timezone.utc))

    def active_geometry_revision(self) -> AssessmentAreaGeometryRevision:
        revision = next((item for item in self.geometry_revisions if item.id == self.active_geometry_revision_id), None)
        if revision is None:
            raise ValueError(f"Assessment Area {self.id!r} has no active geometry revision")
        return revision

    def links_for_revision(self, revision_id: str | None = None) -> list[AssessmentEventLink]:
        """Links are revision-scoped; historical links remain on the area."""
        target = revision_id or self.active_geometry_revision_id
        return [link for link in self.event_links
                if link.assessment_area_geometry_revision_id == target]

    @property
    def source_dataset_id(self): return self.active_geometry_revision().source_dataset_id
    @property
    def selection_polygon_frozen(self): return self.active_geometry_revision().selection_polygon_frozen
    @property
    def final_geometry_frozen(self): return self.active_geometry_revision().final_geometry_frozen
    @property
    def lower_elevation(self): return self.active_geometry_revision().lower_elevation
    @property
    def upper_elevation(self): return self.active_geometry_revision().upper_elevation
    @property
    def horizon_slices(self): return self.active_geometry_revision().horizon_slices

    def archive(self, reason: str | None = None, archived_at: datetime | None = None) -> None:
        self.is_archived = True
        self.archived_at = archived_at or utc_now()
        self.archive_reason = reason

    def restore(self) -> None:
        self.is_archived = False
        self.archived_at = None
        self.archive_reason = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "assessment_date": self.assessment_date.isoformat(),
            "geometry_revisions": [item.to_dict() for item in self.geometry_revisions],
            "active_geometry_revision_id": self.active_geometry_revision_id,
            "event_links": [item.to_dict() for item in self.event_links],
            "is_archived": self.is_archived,
            "archived_at": _datetime_to_text(self.archived_at),
            "archive_reason": self.archive_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentArea":
        revisions = [AssessmentAreaGeometryRevision.from_dict(item) for item in data.get("geometry_revisions", [])]
        active_id = data.get("active_geometry_revision_id")
        if not revisions:  # migration of PR #28 / existing local prototype JSON
            revision_data = {
                "id": f"{data['id']}-R001", "assessment_area_id": data["id"], "revision_number": 1,
                "created_at": data.get("created_at") or f"{data['assessment_date']}T00:00:00+00:00",
                "source_dataset_id": data["source_dataset_id"],
                "selection_polygon_frozen": data["selection_polygon_frozen"],
                "final_geometry_frozen": data["final_geometry_frozen"],
                "lower_elevation": data["lower_elevation"], "upper_elevation": data["upper_elevation"],
                "horizon_slices": data.get("horizon_slices", []), "change_reason": "Миграция старого формата",
            }
            revisions = [AssessmentAreaGeometryRevision.from_dict(revision_data)]
            active_id = revisions[0].id
        return cls(
            id=data["id"],
            name=data["name"],
            assessment_date=date.fromisoformat(data["assessment_date"]),
            geometry_revisions=revisions,
            active_geometry_revision_id=active_id,
            event_links=[AssessmentEventLink.from_dict(
                item, area_revision_id=active_id,
                fallback_created_at=next((r.created_at for r in revisions if r.id == active_id), revisions[-1].created_at),
            ) for item in data.get("event_links", [])],
            is_archived=bool(data.get("is_archived", False)),
            archived_at=_datetime_from_text(data.get("archived_at")),
            archive_reason=data.get("archive_reason"),
        )
