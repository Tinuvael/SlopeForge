from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from app.localization import settings


BACKUP_DIRECTORY_KEY = "updater/backup_directory"
LAST_BACKUP_KEY = "updater/last_backup"


def default_backup_directory() -> Path:
    documents = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    root = Path(documents) if documents else Path.home()
    return root / "SlopeForge Backups"


def backup_directory(store: QSettings | None = None) -> Path:
    target = store or settings()
    value = str(target.value(BACKUP_DIRECTORY_KEY, "") or "").strip()
    return Path(value).expanduser() if value else default_backup_directory()


def save_backup_directory(path: str | Path, store: QSettings | None = None) -> Path:
    resolved = Path(path).expanduser()
    target = store or settings()
    target.setValue(BACKUP_DIRECTORY_KEY, str(resolved))
    target.sync()
    return resolved


def last_backup(store: QSettings | None = None) -> Path | None:
    target = store or settings()
    value = str(target.value(LAST_BACKUP_KEY, "") or "").strip()
    return Path(value).expanduser() if value else None


def save_last_backup(path: str | Path, store: QSettings | None = None) -> Path:
    resolved = Path(path).expanduser()
    target = store or settings()
    target.setValue(LAST_BACKUP_KEY, str(resolved))
    target.sync()
    return resolved
