from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from typing import Any, Literal, TypeAlias

# Phase 3A compatibility bridge; remove when the remaining domain model moves in Phase 3B.
from domain.geometry.types import (
    DatamineLine, PlanGeometry, PlanLineString, PlanMultiPoint, PlanPoint,
    PlanPolygon, plan_geometry_from_dict,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _datetime_from_text(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None

@dataclass
class ProjectLinesDataset:
    id: str
    name: str
    imported_at: datetime
    source_file_name: str
    is_active: bool
    lines: list[DatamineLine] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "imported_at": self.imported_at.isoformat(),
            "source_file_name": self.source_file_name,
            "is_active": self.is_active,
            "lines": [line.to_dict() for line in self.lines],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectLinesDataset":
        return cls(
            id=data["id"],
            name=data["name"],
            imported_at=datetime.fromisoformat(data["imported_at"]),
            source_file_name=data["source_file_name"],
            is_active=bool(data.get("is_active", False)),
            lines=[DatamineLine.from_dict(item) for item in data.get("lines", [])],
        )


@dataclass
class BlastEventGeometryRevision:
    id: str
    blast_event_id: str
    revision_number: int
    imported_at: datetime
    source_file_name: str
    source_geometry: list[DatamineLine]
    plan_geometry: PlanGeometry
    elevation: float
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "blast_event_id": self.blast_event_id,
            "revision_number": self.revision_number,
            "imported_at": self.imported_at.isoformat(),
            "source_file_name": self.source_file_name,
            "source_geometry": [line.to_dict() for line in self.source_geometry],
            "plan_geometry": self.plan_geometry.to_dict(),
            "elevation": self.elevation,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlastEventGeometryRevision":
        return cls(
            id=data["id"],
            blast_event_id=data["blast_event_id"],
            revision_number=int(data["revision_number"]),
            imported_at=datetime.fromisoformat(data["imported_at"]),
            source_file_name=data["source_file_name"],
            source_geometry=[DatamineLine.from_dict(item) for item in data.get("source_geometry", [])],
            plan_geometry=plan_geometry_from_dict(data["plan_geometry"]),
            elevation=float(data["elevation"]),
            is_active=bool(data.get("is_active", False)),
        )


BlastEventType = Literal["production", "contour"]


@dataclass
class BlastEvent:
    id: str
    name: str
    event_type: BlastEventType
    event_date: date | None
    elevation: float
    geometry_revisions: list[BlastEventGeometryRevision] = field(default_factory=list)
    active_geometry_revision_id: str | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    archive_reason: str | None = None
    blast_block_id: int | None = None

    def __post_init__(self) -> None:
        if self.event_type not in {"production", "contour"}:
            raise ValueError(f"Unsupported BlastEvent type: {self.event_type!r}")

    def add_geometry_revision(
        self,
        *,
        source_file_name: str,
        source_geometry: list[DatamineLine],
        plan_geometry: PlanGeometry,
        elevation: float,
        imported_at: datetime | None = None,
    ) -> BlastEventGeometryRevision:
        for revision in self.geometry_revisions:
            revision.is_active = False
        number = max((revision.revision_number for revision in self.geometry_revisions), default=0) + 1
        revision = BlastEventGeometryRevision(
            id=f"{self.id}-R{number:03d}",
            blast_event_id=self.id,
            revision_number=number,
            imported_at=imported_at or utc_now(),
            source_file_name=source_file_name,
            source_geometry=[DatamineLine.from_dict(line.to_dict()) for line in source_geometry],
            plan_geometry=plan_geometry,
            elevation=float(elevation),
            is_active=True,
        )
        self.geometry_revisions.append(revision)
        self.active_geometry_revision_id = revision.id
        return revision

    def active_geometry_revision(self) -> BlastEventGeometryRevision | None:
        return next(
            (revision for revision in self.geometry_revisions if revision.id == self.active_geometry_revision_id),
            None,
        )

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
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "elevation": self.elevation,
            "blast_block_id": self.blast_block_id,
            "geometry_revisions": [revision.to_dict() for revision in self.geometry_revisions],
            "active_geometry_revision_id": self.active_geometry_revision_id,
            "is_archived": self.is_archived,
            "archived_at": _datetime_to_text(self.archived_at),
            "archive_reason": self.archive_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlastEvent":
        return cls(
            id=data["id"],
            name=data["name"],
            event_type=data["event_type"],
            event_date=date.fromisoformat(data["event_date"]) if data.get("event_date") else None,
            elevation=float(data["elevation"]),
            blast_block_id=data.get("blast_block_id"),
            geometry_revisions=[BlastEventGeometryRevision.from_dict(item) for item in data.get("geometry_revisions", [])],
            active_geometry_revision_id=data.get("active_geometry_revision_id"),
            is_archived=bool(data.get("is_archived", False)),
            archived_at=_datetime_from_text(data.get("archived_at")),
            archive_reason=data.get("archive_reason"),
        )


HorizonSliceRole = Literal["lower_boundary", "internal_horizon", "upper_boundary"]
LinkStatus = Literal["suggested", "confirmed", "excluded"]
LinkSource = Literal["automatic", "manual"]


AttachmentOwnerType = Literal["blast_event", "assessment_evaluation"]
AttachmentKind = Literal["photo", "document"]


@dataclass
class EntityAttachment:
    """Metadata for one physical file owned by exactly one stable entity."""
    id: str
    owner_type: AttachmentOwnerType
    owner_id: str
    attachment_kind: AttachmentKind
    subtype: str
    custom_subtype: str
    title: str
    original_filename: str
    stored_filename: str
    relative_path: str
    file_date: date
    description: str
    mime_type: str
    file_size_bytes: int
    created_at: datetime

    def __post_init__(self) -> None:
        if self.owner_type not in {"blast_event", "assessment_evaluation"}:
            raise ValueError(f"Unsupported attachment owner: {self.owner_type!r}")
        if self.attachment_kind not in {"photo", "document"}:
            raise ValueError(f"Unsupported attachment kind: {self.attachment_kind!r}")
        if Path(self.relative_path).is_absolute():
            raise ValueError("Attachment paths must be relative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "owner_type": self.owner_type, "owner_id": self.owner_id,
            "attachment_kind": self.attachment_kind, "subtype": self.subtype,
            "custom_subtype": self.custom_subtype, "title": self.title,
            "original_filename": self.original_filename, "stored_filename": self.stored_filename,
            "relative_path": self.relative_path, "file_date": self.file_date.isoformat(),
            "description": self.description, "mime_type": self.mime_type,
            "file_size_bytes": self.file_size_bytes, "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityAttachment":
        values = dict(data)
        values["file_date"] = date.fromisoformat(values["file_date"])
        values["created_at"] = datetime.fromisoformat(values["created_at"])
        values.setdefault("custom_subtype", "")
        return cls(**values)


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


@dataclass
class AssessmentDomainState:
    datasets: list[ProjectLinesDataset] = field(default_factory=list)
    blast_events: list[BlastEvent] = field(default_factory=list)
    assessment_areas: list[AssessmentArea] = field(default_factory=list)
    technical_cards: list[Any] = field(default_factory=list)
    evaluations: list[Any] = field(default_factory=list)
    attachments: list[EntityAttachment] = field(default_factory=list)

    def add_dataset(self, dataset: ProjectLinesDataset, make_active: bool = True) -> None:
        if any(item.id == dataset.id for item in self.datasets):
            raise ValueError(f"Dataset {dataset.id!r} already exists")
        if make_active:
            for item in self.datasets:
                item.is_active = False
            dataset.is_active = True
        self.datasets.append(dataset)

    def active_dataset(self) -> ProjectLinesDataset | None:
        return next((dataset for dataset in self.datasets if dataset.is_active), None)

    def active_blast_events(self) -> list[BlastEvent]:
        return [event for event in self.blast_events if not event.is_archived]

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasets": [dataset.to_dict() for dataset in self.datasets],
            "blast_events": [event.to_dict() for event in self.blast_events],
            "assessment_areas": [area.to_dict() for area in self.assessment_areas],
            "technical_cards": [card.to_dict() for card in self.technical_cards],
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentDomainState":
        # Local import keeps the technical-card layer separate from the geometry core.
        from .technical_card import BlastEventTechnicalCard
        from .wall_assessment import AssessmentAreaEvaluation
        return cls(
            datasets=[ProjectLinesDataset.from_dict(item) for item in data.get("datasets", [])],
            blast_events=[BlastEvent.from_dict(item) for item in data.get("blast_events", [])],
            assessment_areas=[AssessmentArea.from_dict(item) for item in data.get("assessment_areas", [])],
            technical_cards=[BlastEventTechnicalCard.from_dict(item) for item in data.get("technical_cards", [])],
            evaluations=[AssessmentAreaEvaluation.from_dict(item) for item in data.get("evaluations", [])],
            attachments=[EntityAttachment.from_dict(item) for item in data.get("attachments", [])],
        )
