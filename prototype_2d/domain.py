from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal, TypeAlias

from .models import DatamineLine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_timezone(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")


def _datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _datetime_from_text(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    _require_timezone(parsed, "serialized datetime")
    return parsed


@dataclass(frozen=True)
class PlanPoint:
    x: float
    y: float

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Point", "coordinates": [self.x, self.y]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanPoint":
        x, y = data["coordinates"]
        return cls(float(x), float(y))


@dataclass(frozen=True)
class PlanLineString:
    points: tuple[PlanPoint, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("LineString requires at least two points")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "LineString", "coordinates": [[point.x, point.y] for point in self.points]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanLineString":
        return cls(tuple(PlanPoint(float(x), float(y)) for x, y in data["coordinates"]))


@dataclass(frozen=True)
class PlanPolygon:
    ring: tuple[PlanPoint, ...]

    def __post_init__(self) -> None:
        if len(self.ring) < 4:
            raise ValueError("Polygon ring requires at least three vertices and a closing point")
        if self.ring[0] != self.ring[-1]:
            raise ValueError("Polygon ring must be closed")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Polygon", "coordinates": [[[point.x, point.y] for point in self.ring]]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanPolygon":
        coordinates = data["coordinates"][0]
        return cls(tuple(PlanPoint(float(x), float(y)) for x, y in coordinates))


@dataclass(frozen=True)
class PlanMultiPoint:
    points: tuple[PlanPoint, ...]

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("MultiPoint requires at least one point")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "MultiPoint", "coordinates": [[point.x, point.y] for point in self.points]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanMultiPoint":
        return cls(tuple(PlanPoint(float(x), float(y)) for x, y in data["coordinates"]))


PlanGeometry: TypeAlias = PlanPoint | PlanLineString | PlanPolygon | PlanMultiPoint


def plan_geometry_from_dict(data: dict[str, Any]) -> PlanGeometry:
    geometry_type = data.get("type")
    factories = {
        "Point": PlanPoint.from_dict,
        "LineString": PlanLineString.from_dict,
        "Polygon": PlanPolygon.from_dict,
        "MultiPoint": PlanMultiPoint.from_dict,
    }
    try:
        return factories[geometry_type](data)
    except KeyError as exc:
        raise ValueError(f"Unsupported plan geometry type: {geometry_type!r}") from exc


@dataclass
class ProjectLinesDataset:
    id: str
    name: str
    imported_at: datetime
    source_file_name: str
    is_active: bool
    lines: list[DatamineLine] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_timezone(self.imported_at, "ProjectLinesDataset.imported_at")

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

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("BlastEventGeometryRevision id is required")
        if not self.blast_event_id:
            raise ValueError("BlastEventGeometryRevision blast_event_id is required")
        if self.revision_number < 1:
            raise ValueError("BlastEventGeometryRevision revision_number must be positive")
        _require_timezone(self.imported_at, "BlastEventGeometryRevision.imported_at")

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

    def __post_init__(self) -> None:
        if self.event_type not in {"production", "contour"}:
            raise ValueError(f"Unsupported BlastEvent type: {self.event_type!r}")
        if self.archived_at is not None:
            _require_timezone(self.archived_at, "BlastEvent.archived_at")
        self._validate_geometry_revisions()

    def _validate_geometry_revisions(self) -> None:
        if not self.geometry_revisions:
            if self.active_geometry_revision_id is not None:
                raise ValueError("BlastEvent has an active revision id but no geometry revisions")
            return

        revision_ids = [revision.id for revision in self.geometry_revisions]
        if len(revision_ids) != len(set(revision_ids)):
            raise ValueError("BlastEvent geometry revision ids must be unique")
        if any(revision.blast_event_id != self.id for revision in self.geometry_revisions):
            raise ValueError("BlastEvent geometry revision belongs to another BlastEvent")
        expected_geometry_type = PlanPolygon if self.event_type == "production" else PlanMultiPoint
        if any(not isinstance(revision.plan_geometry, expected_geometry_type) for revision in self.geometry_revisions):
            raise ValueError(f"{self.event_type} BlastEvent geometry revisions have an invalid plan geometry type")
        numbers = sorted(revision.revision_number for revision in self.geometry_revisions)
        if numbers != list(range(1, len(self.geometry_revisions) + 1)):
            raise ValueError("BlastEvent revision numbers must be unique and consecutive starting at 1")
        active_revisions = [revision for revision in self.geometry_revisions if revision.is_active]
        if len(active_revisions) != 1:
            raise ValueError("BlastEvent must have exactly one active geometry revision")
        if self.active_geometry_revision_id != active_revisions[0].id:
            raise ValueError("BlastEvent active_geometry_revision_id must identify the active revision")

    def add_geometry_revision(
        self,
        *,
        source_file_name: str,
        source_geometry: list[DatamineLine],
        plan_geometry: PlanGeometry,
        elevation: float,
        imported_at: datetime | None = None,
    ) -> BlastEventGeometryRevision:
        self._validate_geometry_revisions()
        expected_geometry_type = PlanPolygon if self.event_type == "production" else PlanMultiPoint
        if not isinstance(plan_geometry, expected_geometry_type):
            raise ValueError(f"{self.event_type} BlastEvent requires {expected_geometry_type.__name__} plan geometry")
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
        _require_timezone(self.archived_at, "BlastEvent.archived_at")
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
        )


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

    def __post_init__(self) -> None:
        if not self.blast_event_id:
            raise ValueError("AssessmentEventLink blast_event_id is required")
        if not self.geometry_revision_id:
            raise ValueError("AssessmentEventLink geometry_revision_id is required")
        if self.status not in {"suggested", "confirmed", "excluded"}:
            raise ValueError(f"Unsupported link status: {self.status!r}")
        if self.source not in {"automatic", "manual"}:
            raise ValueError(f"Unsupported link source: {self.source!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "blast_event_id": self.blast_event_id,
            "geometry_revision_id": self.geometry_revision_id,
            "status": self.status,
            "source": self.source,
            "frozen_intersection_geometry": (
                self.frozen_intersection_geometry.to_dict() if self.frozen_intersection_geometry else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentEventLink":
        geometry_data = data.get("frozen_intersection_geometry")
        return cls(
            blast_event_id=data["blast_event_id"],
            geometry_revision_id=data["geometry_revision_id"],
            status=data.get("status", "suggested"),
            source=data.get("source", "automatic"),
            frozen_intersection_geometry=plan_geometry_from_dict(geometry_data) if geometry_data else None,
        )


@dataclass
class AssessmentArea:
    id: str
    name: str
    assessment_date: date
    source_dataset_id: str
    selection_polygon_frozen: PlanPolygon
    final_geometry_frozen: PlanPolygon
    lower_elevation: float
    upper_elevation: float
    horizon_slices: list[AssessmentHorizonSlice] = field(default_factory=list)
    event_links: list[AssessmentEventLink] = field(default_factory=list)
    is_archived: bool = False
    archived_at: datetime | None = None
    archive_reason: str | None = None

    def __post_init__(self) -> None:
        if self.lower_elevation >= self.upper_elevation:
            raise ValueError("AssessmentArea lower_elevation must be below upper_elevation")
        if self.archived_at is not None:
            _require_timezone(self.archived_at, "AssessmentArea.archived_at")

    def archive(self, reason: str | None = None, archived_at: datetime | None = None) -> None:
        self.is_archived = True
        self.archived_at = archived_at or utc_now()
        _require_timezone(self.archived_at, "AssessmentArea.archived_at")
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
            "source_dataset_id": self.source_dataset_id,
            "selection_polygon_frozen": self.selection_polygon_frozen.to_dict(),
            "final_geometry_frozen": self.final_geometry_frozen.to_dict(),
            "lower_elevation": self.lower_elevation,
            "upper_elevation": self.upper_elevation,
            "horizon_slices": [item.to_dict() for item in self.horizon_slices],
            "event_links": [item.to_dict() for item in self.event_links],
            "is_archived": self.is_archived,
            "archived_at": _datetime_to_text(self.archived_at),
            "archive_reason": self.archive_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentArea":
        selection = plan_geometry_from_dict(data["selection_polygon_frozen"])
        final = plan_geometry_from_dict(data["final_geometry_frozen"])
        if not isinstance(selection, PlanPolygon) or not isinstance(final, PlanPolygon):
            raise ValueError("AssessmentArea frozen geometries must be Polygons")
        return cls(
            id=data["id"],
            name=data["name"],
            assessment_date=date.fromisoformat(data["assessment_date"]),
            source_dataset_id=data["source_dataset_id"],
            selection_polygon_frozen=selection,
            final_geometry_frozen=final,
            lower_elevation=float(data["lower_elevation"]),
            upper_elevation=float(data["upper_elevation"]),
            horizon_slices=[AssessmentHorizonSlice.from_dict(item) for item in data.get("horizon_slices", [])],
            event_links=[AssessmentEventLink.from_dict(item) for item in data.get("event_links", [])],
            is_archived=bool(data.get("is_archived", False)),
            archived_at=_datetime_from_text(data.get("archived_at")),
            archive_reason=data.get("archive_reason"),
        )


@dataclass
class AssessmentDomainState:
    datasets: list[ProjectLinesDataset] = field(default_factory=list)
    blast_events: list[BlastEvent] = field(default_factory=list)
    assessment_areas: list[AssessmentArea] = field(default_factory=list)

    def __post_init__(self) -> None:
        dataset_ids = [dataset.id for dataset in self.datasets]
        if len(dataset_ids) != len(set(dataset_ids)):
            raise ValueError("ProjectLinesDataset ids must be unique")
        if len([dataset for dataset in self.datasets if dataset.is_active]) > 1:
            raise ValueError("AssessmentDomainState can have only one active ProjectLinesDataset")

    def add_dataset(self, dataset: ProjectLinesDataset, make_active: bool = True) -> None:
        if any(item.id == dataset.id for item in self.datasets):
            raise ValueError(f"Dataset {dataset.id!r} already exists")
        if make_active:
            for item in self.datasets:
                item.is_active = False
            dataset.is_active = True
        elif dataset.is_active and self.active_dataset() is not None:
            raise ValueError("AssessmentDomainState can have only one active ProjectLinesDataset")
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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentDomainState":
        return cls(
            datasets=[ProjectLinesDataset.from_dict(item) for item in data.get("datasets", [])],
            blast_events=[BlastEvent.from_dict(item) for item in data.get("blast_events", [])],
            assessment_areas=[AssessmentArea.from_dict(item) for item in data.get("assessment_areas", [])],
        )
