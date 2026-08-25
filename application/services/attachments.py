"""Simple, entity-owned attachment metadata plus optional physical file storage."""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from application.state.assessment_domain_state import AssessmentDomainState
from domain.attachments.entities import EntityAttachment
from domain.attachments.policy import (
    ATTACHMENT_CATEGORIES,
    KIND_FOLDERS,
    PHOTO_EXTENSIONS,
    validate_attachment_owner,
)
from infrastructure.desktop.file_opener import open_local_path
from infrastructure.files.attachments import AttachmentFileStorage
from infrastructure.files.storage_availability import (
    DATABASE_ONLY_STORAGE_MESSAGE,
    FileStorageUnavailableError,
)


@dataclass(frozen=True)
class AttachmentDeleteResult:
    cleanup_warning: str | None = None


class EntityAttachmentService:
    def __init__(
        self,
        state: AssessmentDomainState,
        storage_path=None,
        save_callback: Callable[[], None] | None = None,
        *,
        on_add: Callable[[list[EntityAttachment]], None] | None = None,
        on_update: Callable[[EntityAttachment], None] | None = None,
        on_delete: Callable[[EntityAttachment], None] | None = None,
        storage_enabled: bool = True,
    ):
        self.state = state
        if storage_enabled:
            if storage_path is None:
                storage_path = Path.home() / ".config" / "SlopeForge" / "slopeforge_state.json"
            self.storage_path = Path(storage_path)
            self.data_root: Path | None = self.storage_path.parent
        else:
            self.storage_path = None
            self.data_root = None
        self.file_storage = AttachmentFileStorage(self.data_root)
        self.save_callback = save_callback
        self.on_add = on_add
        self.on_update = on_update
        self.on_delete = on_delete

    @property
    def storage_available(self) -> bool:
        return self.file_storage.available

    @property
    def storage_unavailable_message(self) -> str:
        return DATABASE_ONLY_STORAGE_MESSAGE

    def _require_storage(self) -> None:
        if not self.storage_available:
            raise FileStorageUnavailableError(DATABASE_ONLY_STORAGE_MESSAGE)

    @staticmethod
    def _validate(owner_type: str, owner_id: str, attachment_kind: str | None = None) -> None:
        validate_attachment_owner(owner_type, owner_id, attachment_kind)

    def owner_folder(self, owner_type: str, owner_id: str, create: bool = True) -> Path:
        self._require_storage()
        return self.file_storage.owner_folder(owner_type, owner_id, create)

    def attachment_folder(
        self,
        owner_type: str,
        owner_id: str,
        attachment_kind: str,
        create: bool = True,
    ) -> Path:
        self._require_storage()
        self._validate(owner_type, owner_id, attachment_kind)
        owner = self.owner_folder(owner_type, owner_id, create=create)
        folder = owner / KIND_FOLDERS[attachment_kind]
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _destination(self, owner_type: str, owner_id: str, kind: str, filename: str) -> Path:
        self._require_storage()
        return self.file_storage.destination(owner_type, owner_id, kind, filename)

    @staticmethod
    def _file_date(source: Path, kind: str) -> date:
        del kind
        try:
            return datetime.fromtimestamp(source.stat().st_mtime).date()
        except OSError:
            return date.today()

    def add_files(
        self,
        owner_type: str,
        owner_id: str,
        attachment_kind: str,
        source_paths: Iterable[str | Path],
        metadata: dict | None = None,
    ) -> list[EntityAttachment]:
        metadata = metadata or {}
        return self.add_files_with_metadata(
            owner_type,
            owner_id,
            attachment_kind,
            ((source, metadata) for source in source_paths),
        )

    def add_files_with_metadata(
        self,
        owner_type: str,
        owner_id: str,
        attachment_kind: str,
        entries: Iterable[tuple[str | Path, dict | None]],
    ) -> list[EntityAttachment]:
        self._require_storage()
        self._validate(owner_type, owner_id, attachment_kind)
        root = self.data_root
        if root is None:
            raise FileStorageUnavailableError(DATABASE_ONLY_STORAGE_MESSAGE)
        added: list[EntityAttachment] = []
        destinations: list[Path] = []
        try:
            for raw_source, raw_metadata in entries:
                metadata = raw_metadata or {}
                source = Path(raw_source)
                if not source.is_file():
                    raise FileNotFoundError(source)
                destination = self._destination(
                    owner_type, owner_id, attachment_kind, source.name
                )
                destinations.append(destination)
                self.file_storage.copy(source, destination)
                relative = destination.relative_to(root).as_posix()
                attachment = EntityAttachment(
                    id=f"ATT-{uuid4().hex[:12].upper()}",
                    owner_type=owner_type,
                    owner_id=owner_id,
                    attachment_kind=attachment_kind,
                    subtype=metadata.get("subtype", "other"),
                    custom_subtype=metadata.get("custom_subtype", ""),
                    title=metadata.get("title") or source.stem,
                    original_filename=source.name,
                    stored_filename=destination.name,
                    relative_path=relative,
                    file_date=metadata.get("file_date")
                    or self._file_date(source, attachment_kind),
                    description=metadata.get("description", ""),
                    mime_type=mimetypes.guess_type(source.name)[0]
                    or "application/octet-stream",
                    file_size_bytes=destination.stat().st_size,
                    created_at=datetime.now(timezone.utc),
                )
                self.state.attachments.append(attachment)
                added.append(attachment)
            if self.on_add:
                self.on_add(added)
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

    def list_for_owner(
        self,
        owner_type: str,
        owner_id: str,
        attachment_kind: str | None = None,
    ):
        self._validate(owner_type, owner_id, attachment_kind)
        result = [
            a
            for a in self.state.attachments
            if a.owner_type == owner_type
            and a.owner_id == owner_id
            and (attachment_kind is None or a.attachment_kind == attachment_kind)
        ]
        return sorted(result, key=lambda a: (-a.file_date.toordinal(), a.title.casefold()))

    def resolve_path(self, attachment: EntityAttachment) -> Path:
        if not self.storage_available:
            # Metadata-only mode must not probe the original network/share path.
            # Return a deterministic nonexistent local placeholder so existing
            # read-only Qt views can still render filenames/icons safely.
            safe_name = Path(attachment.stored_filename or attachment.original_filename).name
            return Path(".slopeforge-file-unavailable") / safe_name
        return self.file_storage.resolve(attachment)

    def is_missing(self, attachment: EntityAttachment) -> bool:
        if not self.storage_available:
            return True
        return not self.resolve_path(attachment).is_file()

    def update_metadata(
        self,
        attachment_id: str,
        *,
        title: str,
        file_date: date,
        subtype: str,
        description: str,
        custom_subtype: str = "",
    ) -> EntityAttachment:
        attachment = self._find(attachment_id)
        fields = ("title", "file_date", "subtype", "description", "custom_subtype")
        previous = {field: getattr(attachment, field) for field in fields}
        attachment.title = title.strip() or Path(attachment.original_filename).stem
        attachment.file_date = file_date
        attachment.subtype = subtype
        attachment.description = description
        attachment.custom_subtype = custom_subtype
        try:
            self.on_update(attachment) if self.on_update else self._save()
        except Exception:
            for field, value in previous.items():
                setattr(attachment, field, value)
            raise
        return attachment

    def delete_attachment(self, attachment_id: str) -> AttachmentDeleteResult:
        self._require_storage()
        attachment = self._find(attachment_id)
        path = self.resolve_path(attachment)
        index = self.state.attachments.index(attachment)
        temporary = self.file_storage.stage_delete(path)
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
                return AttachmentDeleteResult(f"{temporary}: {cleanup_exc}")
        return AttachmentDeleteResult()

    def open_file(self, attachment: EntityAttachment) -> bool:
        self._require_storage()
        path = self.resolve_path(attachment)
        return path.is_file() and open_local_path(path)

    def open_owner_folder(self, owner_type: str, owner_id: str) -> bool:
        self._require_storage()
        return open_local_path(self.owner_folder(owner_type, owner_id))

    def open_attachment_folder(
        self, owner_type: str, owner_id: str, attachment_kind: str
    ) -> bool:
        self._require_storage()
        return open_local_path(
            self.attachment_folder(owner_type, owner_id, attachment_kind)
        )

    def counts(self, owner_type: str, owner_id: str) -> tuple[int, int]:
        items = self.list_for_owner(owner_type, owner_id)
        return (
            sum(a.attachment_kind == "photo" for a in items),
            sum(a.attachment_kind == "document" for a in items),
        )

    def _find(self, attachment_id: str) -> EntityAttachment:
        attachment = next(
            (a for a in self.state.attachments if a.id == attachment_id), None
        )
        if attachment is None:
            raise KeyError(attachment_id)
        return attachment

    def _save(self) -> None:
        if self.save_callback:
            self.save_callback()