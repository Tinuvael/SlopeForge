from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal
from domain.geometry.types import DatamineLine, PlanGeometry, plan_geometry_from_dict

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None

def _datetime_from_text(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None

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
    comment: str | None = None
    created_by_user_id: int | None = None

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
            "geometry_revisions": [revision.to_dict() for revision in self.geometry_revisions],
            "active_geometry_revision_id": self.active_geometry_revision_id,
            "is_archived": self.is_archived,
            "archived_at": _datetime_to_text(self.archived_at),
            "archive_reason": self.archive_reason,
            "comment": self.comment,
            "created_by_user_id": self.created_by_user_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlastEvent":
        return cls(
            id=data["id"],
            name=data["name"],
            event_type=data["event_type"],
            event_date=date.fromisoformat(data["event_date"]) if data.get("event_date") else None,
            elevation=float(data["elevation"]),
            geometry_revisions=[BlastEventGeometryRevision.from_dict(item) for item in data.get("geometry_revisions", [])],
            active_geometry_revision_id=data.get("active_geometry_revision_id"),
            is_archived=bool(data.get("is_archived", False)),
            archived_at=_datetime_from_text(data.get("archived_at")),
            archive_reason=data.get("archive_reason"),
            comment=data.get("comment"),
            created_by_user_id=data.get("created_by_user_id"),
        )