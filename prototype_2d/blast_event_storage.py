"""JSON-хранилище только для Blast Events Prototype."""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import QStandardPaths
from .domain import AssessmentDomainState


def default_blast_event_storage_path() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base or Path.home() / ".config" / "SlopeForge") / "prototype" / "blast_events.json"


def save_blast_event_state(state: AssessmentDomainState, path: str | Path | None = None) -> Path:
    target = Path(path) if path else default_blast_event_storage_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_blast_event_state(path: str | Path | None = None) -> AssessmentDomainState:
    target = Path(path) if path else default_blast_event_storage_path()
    if not target.exists():
        return AssessmentDomainState()
    return AssessmentDomainState.from_dict(json.loads(target.read_text(encoding="utf-8")))
