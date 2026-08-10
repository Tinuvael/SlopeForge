"""Framework-independent attachment naming and category policy."""
from __future__ import annotations

import re
from pathlib import Path

OWNER_FOLDERS = {"blast_event": "blast_events", "assessment_evaluation": "assessments"}
KIND_FOLDERS = {"photo": "photos", "document": "documents"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

ATTACHMENT_CATEGORIES = {
    ("blast_event", "photo"): [("before_blast", "Before blast"), ("drilling", "Drilling"), ("charging", "Charging"), ("initiation", "Initiation system installation"), ("after_blast", "After blast"), ("muckpile", "Muckpile"), ("final_wall", "Final wall"), ("contour_drilling", "Contour drilling"), ("other", "Other")],
    ("blast_event", "document"): [("blast_design", "Blast design"), ("drilling_report", "Drilling report"), ("charging_report", "Charging report"), ("initiation_scheme", "Initiation scheme"), ("survey", "Survey"), ("as_built_survey", "As-built survey"), ("geomechanical", "Geomechanical materials"), ("inspection_act", "Inspection record"), ("other", "Other")],
    ("assessment_evaluation", "photo"): [("general_view", "General view"), ("crest", "Crest"), ("toe", "Toe"), ("face", "Face"), ("drillhole_traces", "Contour drillhole traces"), ("cracks", "Cracks"), ("loose_blocks", "Loose blocks / rockfall"), ("berm", "Berm"), ("water", "Water"), ("measurement", "Measurements"), ("other", "Other")],
    ("assessment_evaluation", "document"): [("as_built_survey", "As-built survey"), ("measurement_report", "Measurement report"), ("assessment_form", "Assessment form"), ("inspection_act", "Inspection record"), ("wall_report", "Wall condition report"), ("recommendation", "Recommendations"), ("other", "Other")],
}


def validate_attachment_owner(owner_type: str, owner_id: str, attachment_kind: str | None = None) -> None:
    if owner_type not in OWNER_FOLDERS:
        raise ValueError("Неизвестный тип владельца файла")
    if not owner_id or owner_id in {".", ".."} or Path(owner_id).name != owner_id or "/" in owner_id or "\\" in owner_id:
        raise ValueError("Некорректный ID владельца")
    if attachment_kind is not None and attachment_kind not in KIND_FOLDERS:
        raise ValueError("Неизвестный тип файла")


def sanitize_filename(filename: str) -> str:
    """Return a readable cross-platform basename, never a path."""
    name = Path(filename.replace("\\", "/")).name
    stem, suffix = Path(name).stem, Path(name).suffix
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")
    suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix)
    return f"{stem or 'file'}{suffix.lower()}"
