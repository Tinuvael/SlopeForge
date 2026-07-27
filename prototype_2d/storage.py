from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from .models import PrototypeState


def default_storage_path() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation) or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if not base:
        base = str(Path.home() / ".config" / "SlopeForge")
    return Path(base) / "prototype" / "line_segment_prototype.json"


def save_state(state: PrototypeState, path: str | Path | None = None) -> Path:
    target = Path(path) if path else default_storage_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_state(path: str | Path | None = None) -> PrototypeState:
    source = Path(path) if path else default_storage_path()
    return PrototypeState.from_dict(json.loads(source.read_text(encoding="utf-8")))
