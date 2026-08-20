from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from sqlalchemy.engine import make_url

from .env import load_local_env


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_root: Path

    @classmethod
    def from_values(cls, database_url: str, storage_root: str | Path) -> "Settings":
        database_url = str(database_url or "").strip()
        storage_text = str(storage_root or "").strip()
        missing = []
        if not database_url:
            missing.append("DATABASE_URL")
        if not storage_text:
            missing.append("STORAGE_ROOT")
        if missing:
            raise ConfigurationError(
                "Missing required setting(s): " + ", ".join(missing)
            )
        if not database_url.startswith("postgresql+psycopg://"):
            raise ConfigurationError(
                "DATABASE_URL must use PostgreSQL with psycopg 3, for example: "
                "postgresql+psycopg://user:password@host:5432/slopeforge"
            )
        return cls(database_url=database_url, storage_root=Path(storage_text).expanduser())

    @classmethod
    def from_env(cls) -> "Settings":
        load_local_env()
        return cls.from_values(
            os.getenv("DATABASE_URL", ""),
            os.getenv("STORAGE_ROOT", ""),
        )


def safe_database_location(database_url: str) -> str:
    """Return DATABASE_URL location without password for UI messages."""
    url = make_url(database_url)
    host = url.host or "localhost"
    port = f":{url.port}" if url.port else ""
    database = url.database or ""
    username = f"{url.username}@" if url.username else ""
    return f"{username}{host}{port}/{database}"
