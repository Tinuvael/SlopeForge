from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

SEGMENT_ROLES = ("upper_boundary", "lower_boundary", "intermediate_assessment")
DRAFT_STATUSES = ("not_assessed", "assessed_placeholder")


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
    elevation: float
    source_type: str | None = None
    assigned_type: str | None = None
    source_file: str | None = None
    import_order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "points": [p.to_dict() for p in self.points]}

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
    elevation: float
    comment: str = ""

    def __post_init__(self) -> None:
        if self.role not in SEGMENT_ROLES:
            raise ValueError(f"Unknown segment role: {self.role}")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "extracted_points": [p.to_dict() for p in self.extracted_points]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineSegmentSelection":
        copied = dict(data)
        copied["extracted_points"] = [DataminePoint.from_dict(p) for p in copied.get("extracted_points", [])]
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

    def elevations(self) -> list[float]:
        return sorted({line.elevation for line in self.lines})

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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrototypeState":
        return cls(
            imported_csv=data.get("imported_csv"),
            lines=[DatamineLine.from_dict(item) for item in data.get("lines", [])],
            segments=[LineSegmentSelection.from_dict(item) for item in data.get("segments", [])],
            drafts=[BenchSectionDraft.from_dict(item) for item in data.get("drafts", [])],
        )
