"""Simple, entity-owned file storage beside the application state anchor."""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from domain.attachments.entities import EntityAttachment
from domain.attachments.policy import (
    ATTACHMENT_CATEGORIES,
    PHOTO_EXTENSIONS,
    sanitize_filename,
    validate_attachment_owner,
)
from infrastructure.desktop.file_opener import open_local_path
from infrastructure.files.attachments import AttachmentFileStorage
from application.state.assessment_domain_state import AssessmentDomainState

@dataclass(frozen=True)
class AttachmentDeleteResult:
    """A logical delete may succeed even if its temporary file needs later cleanup."""

    cleanup_warning: str | None = None

class EntityAttachmentService:
    def __init__(self, state: AssessmentDomainState, storage_path=None,
                 save_callback: Callable[[], None] | None = None, *,
                 on_add: Callable[[EntityAttachment], None] | None = None,
                 on_update: Callable[[EntityAttachment], None] | None = None,
                 on_delete: Callable[[EntityAttachment], None] | None = None):
        self.state = state
        if storage_path is None:
            storage_path = Path.home() / ".config" / "SlopeForge" / "slopeforge_state.json"
        self.storage_path = Path(storage_path)
        self.data_root = self.storage_path.parent
        self.file_storage = AttachmentFileStorage(self.data_root)
        self.save_callback = save_callback
        self.on_add, self.on_update, self.on_delete = on_add, on_update, on_delete

    @staticmethod
    def _validate(owner_type: str, owner_id: str, attachment_kind: str | None = None) -> None:
        validate_attachment_owner(owner_type, owner_id, attachment_kind)

    def owner_folder(self, owner_type: str, owner_id: str, create: bool = True) -> Path:
        return self.file_storage.owner_folder(owner_type, owner_id, create)

    def _destination(self, owner_type: str, owner_id: str, kind: str, filename: str) -> Path:
        return self.file_storage.destination(owner_type, owner_id, kind, filename)

    @staticmethod
    def _file_date(source: Path, kind: str) -> date:
        try:
            return datetime.fromtimestamp(source.stat().st_mtime).date()
        except OSError:
            return date.today()

    def add_files(self, owner_type: str, owner_id: str, attachment_kind: str,
                  source_paths: Iterable[str | Path], metadata: dict | None = None) -> list[EntityAttachment]:
        self._validate(owner_type, owner_id, attachment_kind)
        metadata = metadata or {}
        added: list[EntityAttachment] = []
        destinations: list[Path] = []
        try:
            for raw_source in source_paths:
                source = Path(raw_source)
                if not source.is_file():
                    raise FileNotFoundError(source)
                destination = self._destination(owner_type, owner_id, attachment_kind, source.name)
                # The destination did not exist when selected by _destination, so it
                # is safe to remove it if this batch later fails.
                destinations.append(destination)
                self.file_storage.copy(source, destination)
                relative = destination.relative_to(self.data_root).as_posix()
                attachment = EntityAttachment(
                    id=f"ATT-{uuid4().hex[:12].upper()}", owner_type=owner_type, owner_id=owner_id,
                    attachment_kind=attachment_kind, subtype=metadata.get("subtype", "other"),
                    custom_subtype=metadata.get("custom_subtype", ""),
                    title=metadata.get("title") or source.stem, original_filename=source.name,
                    stored_filename=destination.name, relative_path=relative,
                    file_date=metadata.get("file_date") or self._file_date(source, attachment_kind),
                    description=metadata.get("description", ""),
                    mime_type=mimetypes.guess_type(source.name)[0] or "application/octet-stream",
                    file_size_bytes=destination.stat().st_size, created_at=datetime.now(timezone.utc),
                )
                self.state.attachments.append(attachment)
                added.append(attachment)
            if self.on_add:
                for attachment in added: self.on_add(attachment)
            else:
                self._save()
            return added
        except Exception as exc:
            for attachment in added:
                if attachment in self.state.attachments:
                    self.state.attachments.remove(attachment)
            cleanup_errors = []
            for destination in reversed(destinations):
                try:
                    if destination.exists():
                        self.file_storage.remove(destination)
                except OSError as cleanup_exc:
                    cleanup_errors.append(cleanup_exc)
            if cleanup_errors:
                raise RuntimeError(
                    f"Attachment import failed and cleanup also failed: {cleanup_errors[0]}"
                ) from exc
            raise

    def list_for_owner(self, owner_type: str, owner_id: str, attachment_kind: str | None = None):
        self._validate(owner_type, owner_id, attachment_kind)
        result = [a for a in self.state.attachments if a.owner_type == owner_type and a.owner_id == owner_id and (attachment_kind is None or a.attachment_kind == attachment_kind)]
        return sorted(result, key=lambda a: (-a.file_date.toordinal(), a.title.casefold()))

    def resolve_path(self, attachment: EntityAttachment) -> Path:
        return self.file_storage.resolve(attachment)

    def is_missing(self, attachment: EntityAttachment) -> bool:
        return not self.resolve_path(attachment).is_file()

    def update_metadata(self, attachment_id: str, *, title: str, file_date: date,
                        subtype: str, description: str, custom_subtype: str = "") -> EntityAttachment:
        attachment = self._find(attachment_id)
        fields = ("title", "file_date", "subtype", "description", "custom_subtype")
        previous = {field: getattr(attachment, field) for field in fields}
        attachment.title, attachment.file_date = title.strip() or Path(attachment.original_filename).stem, file_date
        attachment.subtype, attachment.description, attachment.custom_subtype = subtype, description, custom_subtype
        try:
            self.on_update(attachment) if self.on_update else self._save()
        except Exception:
            for field, value in previous.items():
                setattr(attachment, field, value)
            raise
        return attachment

    def delete_attachment(self, attachment_id: str) -> AttachmentDeleteResult:
        attachment = self._find(attachment_id)
        path = self.resolve_path(attachment)
        index = self.state.attachments.index(attachment)
        temporary = self.file_storage.stage_delete(path)  # state is untouched if moving the file fails
        self.state.attachments.pop(index)
        try:
            self.on_delete(attachment) if self.on_delete else self._save()
        except Exception as exc:
            self.state.attachments.insert(index, attachment)
            try:
                if temporary is not None and temporary.exists():
                    self.file_storage.restore_delete(temporary, path)
            except OSError as rollback_exc:
                raise RuntimeError(
                    f"Attachment deletion failed and the file could not be restored: {rollback_exc}"
                ) from exc
            raise
        if temporary is not None:
            try:
                self.file_storage.remove(temporary)
            except OSError as cleanup_exc:
                # The database/state commit already succeeded.  This is an orphan
                # cleanup warning, not a failed logical delete.
                return AttachmentDeleteResult(f"{temporary}: {cleanup_exc}")
        return AttachmentDeleteResult()

    def open_file(self, attachment: EntityAttachment) -> bool:
        path = self.resolve_path(attachment)
        return path.is_file() and open_local_path(path)

    def open_owner_folder(self, owner_type: str, owner_id: str) -> bool:
        return open_local_path(self.owner_folder(owner_type, owner_id))

    def counts(self, owner_type: str, owner_id: str) -> tuple[int, int]:
        items = self.list_for_owner(owner_type, owner_id)
        return sum(a.attachment_kind == "photo" for a in items), sum(a.attachment_kind == "document" for a in items)

    def _find(self, attachment_id: str) -> EntityAttachment:
        attachment = next((a for a in self.state.attachments if a.id == attachment_id), None)
        if attachment is None: raise KeyError(attachment_id)
        return attachment

    def _save(self) -> None:
        if self.save_callback: self.save_callback()
