from __future__ import annotations

from dataclasses import dataclass, field, asdict
from statistics import median
from typing import Any

HORIZONTAL_Z_TOLERANCE = 0.05
SEMANTIC_ROLES = ("normal", "pit_boundary")


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
    semantic_role: str = "normal"

    def __post_init__(self) -> None:
        if self.semantic_role not in SEMANTIC_ROLES:
            self.semantic_role = "normal"
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
