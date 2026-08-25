"""Compatibility import for filesystem adapters using the application storage contract."""

from application.file_storage import (
    DATABASE_ONLY_STORAGE_MESSAGE,
    FileStorageUnavailableError,
    optional_data_root,
    require_data_root,
)

__all__ = [
    "DATABASE_ONLY_STORAGE_MESSAGE",
    "FileStorageUnavailableError",
    "optional_data_root",
    "require_data_root",
]
