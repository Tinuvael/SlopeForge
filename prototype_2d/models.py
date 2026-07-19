from __future__ import annotations

from dataclasses import dataclass, field, asdict
from statistics import median
from typing import Any

HORIZONTAL_Z_TOLERANCE = 0.05
SEGMENT_ROLES = ("upper_boundary", "lower_boundary", "intermediate_assessment")
DRAFT_STATUSES = ("not_assessed", "assessed_placeholder")
CANDIDATE_STATUSES = ("suggested", "accepted", "edited", "rejected")


@dataclass
class PrototypeDataset:
    """Неизменяемый набор импортированных исходных линий."""

    id: str
    source_file: str | None = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrototypeDataset":
        return cls(**data)


@dataclass
class DataminePoint:
    x: float
    y: float
    z: float
    source_row_number: int
    pvalue: str | None = None
    extra_values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataminePoint":
        return cls(**data)


@dataclass
class DatamineLine:
    source_id: str
    points: list[DataminePoint]
    elevation: float | None = None
    source_type: str | None = None
    assigned_type: str | None = None
    source_file: str | None = None
    import_order: int = 0
    z_min: float | None = None
    z_max: float | None = None
    z_median: float | None = None
    is_horizontal: bool = False

    def __post_init__(self) -> None:
        self.recalculate_elevation()

    def recalculate_elevation(self, tolerance: float = HORIZONTAL_Z_TOLERANCE) -> None:
        if not self.points:
            self.z_min = self.z_max = self.z_median = self.elevation = None
            self.is_horizontal = False
            return
        z_values = [p.z for p in self.points]
        self.z_min = min(z_values)
        self.z_max = max(z_values)
        self.z_median = float(median(z_values))
        self.is_horizontal = self.z_max - self.z_min <= tolerance
        self.elevation = self.z_median if self.is_horizontal else None

    def display_elevation(self) -> str:
        if self.is_horizontal:
            return f"Z={self.elevation:g}"
        return f"Z={self.z_min:g}…{self.z_max:g}"

    def effective_type(self) -> str | None:
        return self.assigned_type or self.source_type

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["points"] = [p.to_dict() for p in self.points]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DatamineLine":
        copied = dict(data)
        copied["points"] = [DataminePoint.from_dict(p) for p in copied.get("points", [])]
        return cls(**copied)


@dataclass
class LineSegmentSelection:
    id: str
    source_line_id: str
    start_position: float
    end_position: float
    extracted_points: list[DataminePoint]
    role: str
    elevation: float | None
    comment: str = ""
    source_line_ids: list[str] = field(default_factory=list)
    dataset_id: str | None = None

    def __post_init__(self) -> None:
        if self.role not in SEGMENT_ROLES:
            raise ValueError(f"Unknown segment role: {self.role}")
        if not self.source_line_ids:
            self.source_line_ids = [self.source_line_id]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "extracted_points": [p.to_dict() for p in self.extracted_points]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineSegmentSelection":
        copied = dict(data)
        copied["extracted_points"] = [DataminePoint.from_dict(p) for p in copied.get("extracted_points", [])]
        return cls(**copied)


@dataclass
class CandidateIntermediateSegment:
    """Предложенный, но ещё не принятый промежуточный сегмент."""

    id: str
    bench_id: str
    segment: LineSegmentSelection
    status: str = "suggested"

    def __post_init__(self) -> None:
        if self.status not in CANDIDATE_STATUSES:
            raise ValueError(f"Unknown candidate status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "bench_id": self.bench_id, "segment": self.segment.to_dict(), "status": self.status}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateIntermediateSegment":
        copied = dict(data)
        copied["segment"] = LineSegmentSelection.from_dict(copied["segment"])
        return cls(**copied)


@dataclass
class BenchSectionDraft:
    id: str
    upper_segment_id: str
    lower_segment_id: str
    intermediate_segment_ids: list[str] = field(default_factory=list)
    name: str = ""
    comment: str = ""
    status: str = "not_assessed"

    def __post_init__(self) -> None:
        if self.status not in DRAFT_STATUSES:
            raise ValueError(f"Unknown draft status: {self.status}")

    def add_intermediate(self, segment_id: str) -> None:
        if segment_id in self.intermediate_segment_ids:
            raise ValueError("Segment already added to this bench draft")
        self.intermediate_segment_ids.append(segment_id)

    def remove_intermediate(self, segment_id: str) -> None:
        if segment_id in self.intermediate_segment_ids:
            self.intermediate_segment_ids.remove(segment_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchSectionDraft":
        return cls(**data)


@dataclass
class PrototypeState:
    imported_csv: str | None = None
    lines: list[DatamineLine] = field(default_factory=list)
    segments: list[LineSegmentSelection] = field(default_factory=list)
    drafts: list[BenchSectionDraft] = field(default_factory=list)
    datasets: list[PrototypeDataset] = field(default_factory=list)
    active_dataset_id: str | None = None
    candidate_segments: list[CandidateIntermediateSegment] = field(default_factory=list)

    def elevations(self) -> list[float]:
        return sorted({line.elevation for line in self.lines if line.elevation is not None})

    def next_dataset_id(self) -> str:
        return f"D-{len(self.datasets) + 1:03d}"

    def next_candidate_id(self) -> str:
        return f"C-{len(self.candidate_segments) + 1:03d}"

    def next_segment_id(self) -> str:
        return f"S-{len(self.segments) + 1:03d}"

    def next_draft_id(self) -> str:
        return f"U-{len(self.drafts) + 1:03d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "imported_csv": self.imported_csv,
            "lines": [line.to_dict() for line in self.lines],
            "segments": [segment.to_dict() for segment in self.segments],
            "drafts": [draft.to_dict() for draft in self.drafts],
            "datasets": [dataset.to_dict() for dataset in self.datasets],
            "active_dataset_id": self.active_dataset_id,
            "candidate_segments": [candidate.to_dict() for candidate in self.candidate_segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrototypeState":
        return cls(
            imported_csv=data.get("imported_csv"),
            lines=[DatamineLine.from_dict(item) for item in data.get("lines", [])],
            segments=[LineSegmentSelection.from_dict(item) for item in data.get("segments", [])],
            drafts=[BenchSectionDraft.from_dict(item) for item in data.get("drafts", [])],
            datasets=[PrototypeDataset.from_dict(item) for item in data.get("datasets", [])],
            active_dataset_id=data.get("active_dataset_id"),
            candidate_segments=[CandidateIntermediateSegment.from_dict(item) for item in data.get("candidate_segments", [])],
        )
