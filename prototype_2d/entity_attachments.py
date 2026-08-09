"""Simple, entity-owned file storage beside the prototype JSON state."""
from __future__ import annotations

import mimetypes
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from .domain import AssessmentDomainState, EntityAttachment

OWNER_FOLDERS = {"blast_event": "blast_events", "assessment_evaluation": "assessments"}
KIND_FOLDERS = {"photo": "photos", "document": "documents"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

ATTACHMENT_CATEGORIES = {
    ("blast_event", "photo"): [("before_blast", "Before blast"), ("drilling", "Drilling"), ("charging", "Charging"), ("initiation", "Initiation system installation"), ("after_blast", "After blast"), ("muckpile", "Muckpile"), ("final_wall", "Final wall"), ("contour_drilling", "Contour drilling"), ("other", "Other")],
    ("blast_event", "document"): [("blast_design", "Blast design"), ("drilling_report", "Drilling report"), ("charging_report", "Charging report"), ("initiation_scheme", "Initiation scheme"), ("survey", "Survey"), ("as_built_survey", "As-built survey"), ("geomechanical", "Geomechanical materials"), ("inspection_act", "Inspection record"), ("other", "Other")],
    ("assessment_evaluation", "photo"): [("general_view", "General view"), ("crest", "Crest"), ("toe", "Toe"), ("face", "Face"), ("drillhole_traces", "Contour drillhole traces"), ("cracks", "Cracks"), ("loose_blocks", "Loose blocks / rockfall"), ("berm", "Berm"), ("water", "Water"), ("measurement", "Measurements"), ("other", "Other")],
    ("assessment_evaluation", "document"): [("as_built_survey", "As-built survey"), ("measurement_report", "Measurement report"), ("assessment_form", "Assessment form"), ("inspection_act", "Inspection record"), ("wall_report", "Wall condition report"), ("recommendation", "Recommendations"), ("other", "Other")],
}


def sanitize_filename(filename: str) -> str:
    """Return a readable cross-platform basename, never a path."""
    name = Path(filename.replace("\\", "/")).name
    stem, suffix = Path(name).stem, Path(name).suffix
    stem = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", stem).strip(" .")
    suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix)
    return f"{stem or 'file'}{suffix.lower()}"


class EntityAttachmentService:
    def __init__(self, state: AssessmentDomainState, storage_path=None, save_callback: Callable[[], None] | None = None):
        self.state = state
        if storage_path is None:
            from .blast_event_storage import default_blast_event_storage_path
            storage_path = default_blast_event_storage_path()
        self.storage_path = Path(storage_path)
        self.data_root = self.storage_path.parent
        self.save_callback = save_callback

    @staticmethod
    def _validate(owner_type: str, owner_id: str, attachment_kind: str | None = None) -> None:
        if owner_type not in OWNER_FOLDERS:
            raise ValueError("Неизвестный тип владельца файла")
        if not owner_id or owner_id in {".", ".."} or Path(owner_id).name != owner_id or "/" in owner_id or "\\" in owner_id:
            raise ValueError("Некорректный ID владельца")
        if attachment_kind is not None and attachment_kind not in KIND_FOLDERS:
            raise ValueError("Неизвестный тип файла")

    def owner_folder(self, owner_type: str, owner_id: str, create: bool = True) -> Path:
        self._validate(owner_type, owner_id)
        folder = self.data_root / "files" / OWNER_FOLDERS[owner_type] / owner_id
        if create:
            for child in KIND_FOLDERS.values():
                (folder / child).mkdir(parents=True, exist_ok=True)
        return folder

    def _destination(self, owner_type: str, owner_id: str, kind: str, filename: str) -> Path:
        folder = self.owner_folder(owner_type, owner_id) / KIND_FOLDERS[kind]
        safe = sanitize_filename(filename)
        candidate = folder / safe
        number = 2
        while candidate.exists():
            candidate = folder / f"{Path(safe).stem}_{number}{Path(safe).suffix}"
            number += 1
        return candidate

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
        added = []
        for raw_source in source_paths:
            source = Path(raw_source)
            if not source.is_file():
                raise FileNotFoundError(source)
            destination = self._destination(owner_type, owner_id, attachment_kind, source.name)
            shutil.copy2(source, destination)
            if not destination.exists():
                raise OSError(f"Не удалось скопировать {source.name}")
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
            self.state.attachments.append(attachment); added.append(attachment)
        self._save()
        return added

    def list_for_owner(self, owner_type: str, owner_id: str, attachment_kind: str | None = None):
        self._validate(owner_type, owner_id, attachment_kind)
        result = [a for a in self.state.attachments if a.owner_type == owner_type and a.owner_id == owner_id and (attachment_kind is None or a.attachment_kind == attachment_kind)]
        return sorted(result, key=lambda a: (-a.file_date.toordinal(), a.title.casefold()))

    def resolve_path(self, attachment: EntityAttachment) -> Path:
        path = (self.data_root / attachment.relative_path).resolve()
        root = self.data_root.resolve()
        if path != root and root not in path.parents:
            raise ValueError("Путь файла выходит за каталог данных")
        return path

    def is_missing(self, attachment: EntityAttachment) -> bool:
        return not self.resolve_path(attachment).is_file()

    def update_metadata(self, attachment_id: str, *, title: str, file_date: date,
                        subtype: str, description: str, custom_subtype: str = "") -> EntityAttachment:
        attachment = self._find(attachment_id)
        attachment.title, attachment.file_date = title.strip() or Path(attachment.original_filename).stem, file_date
        attachment.subtype, attachment.description, attachment.custom_subtype = subtype, description, custom_subtype
        self._save(); return attachment

    def delete_attachment(self, attachment_id: str) -> None:
        attachment = self._find(attachment_id)
        path = self.resolve_path(attachment)
        if path.exists():
            path.unlink()  # record is deliberately retained if this raises
        self.state.attachments.remove(attachment)
        self._save()

    def open_file(self, attachment: EntityAttachment) -> bool:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        path = self.resolve_path(attachment)
        return path.is_file() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_owner_folder(self, owner_type: str, owner_id: str) -> bool:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.owner_folder(owner_type, owner_id))))

    def counts(self, owner_type: str, owner_id: str) -> tuple[int, int]:
        items = self.list_for_owner(owner_type, owner_id)
        return sum(a.attachment_kind == "photo" for a in items), sum(a.attachment_kind == "document" for a in items)

    def _find(self, attachment_id: str) -> EntityAttachment:
        attachment = next((a for a in self.state.attachments if a.id == attachment_id), None)
        if attachment is None: raise KeyError(attachment_id)
        return attachment

    def _save(self) -> None:
        if self.save_callback: self.save_callback()
