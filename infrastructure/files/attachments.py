"""Physical storage operations for entity-owned attachments (Qt-free)."""
from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from domain.attachments.entities import EntityAttachment
from domain.attachments.policy import KIND_FOLDERS, OWNER_FOLDERS, sanitize_filename, validate_attachment_owner
from infrastructure.files.storage_availability import optional_data_root, require_data_root


class AttachmentFileStorage:
    def __init__(self, data_root: str | Path | None):
        self.data_root = optional_data_root(data_root)

    @property
    def available(self) -> bool:
        return self.data_root is not None

    def owner_folder(self, owner_type: str, owner_id: str, create: bool = True) -> Path:
        validate_attachment_owner(owner_type, owner_id)
        root = require_data_root(self.data_root)
        folder = root / "files" / OWNER_FOLDERS[owner_type] / owner_id
        if create:
            for child in KIND_FOLDERS.values():
                (folder / child).mkdir(parents=True, exist_ok=True)
        return folder

    def destination(self, owner_type: str, owner_id: str, kind: str, filename: str) -> Path:
        folder = self.owner_folder(owner_type, owner_id) / KIND_FOLDERS[kind]
        safe = sanitize_filename(filename)
        candidate = folder / safe
        number = 2
        while candidate.exists():
            candidate = folder / f"{Path(safe).stem}_{number}{Path(safe).suffix}"
            number += 1
        return candidate

    @staticmethod
    def copy(source: Path, destination: Path) -> None:
        shutil.copy2(source, destination)
        if not destination.exists():
            raise OSError(f"Could not copy {source.name}")

    def resolve(self, attachment: EntityAttachment) -> Path:
        root = require_data_root(self.data_root).resolve()
        path = (root / attachment.relative_path).resolve()
        if path != root and root not in path.parents:
            raise ValueError("Attachment path escapes the data directory")
        return path

    @staticmethod
    def remove(path: Path) -> None:
        if path.exists():
            path.unlink()

    @staticmethod
    def stage_delete(path: Path) -> Path | None:
        if not path.exists():
            return None
        temporary = path.with_name(f"{path.name}.slopeforge-delete-{uuid4().hex}.tmp")
        path.replace(temporary)
        return temporary

    @staticmethod
    def restore_delete(temporary: Path | None, original: Path) -> None:
        if temporary is not None and temporary.exists():
            temporary.replace(original)