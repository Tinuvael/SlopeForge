from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal


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
