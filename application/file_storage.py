from __future__ import annotations

from pathlib import Path


class FileStorageUnavailableError(OSError):
    """Physical shared storage is intentionally unavailable for this runtime."""


DATABASE_ONLY_STORAGE_MESSAGE = (
    "Shared file storage is unavailable in Database only mode. "
    "Switch to a Full connection to open, add, delete, or import physical files."
)


def optional_data_root(data_root: str | Path | None) -> Path | None:
    if data_root is None or not str(data_root).strip():
        return None
    return Path(data_root)


def require_data_root(data_root: Path | None) -> Path:
    if data_root is None:
        raise FileStorageUnavailableError(DATABASE_ONLY_STORAGE_MESSAGE)
    return data_root
