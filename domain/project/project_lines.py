from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from domain.geometry.types import DatamineLine

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
