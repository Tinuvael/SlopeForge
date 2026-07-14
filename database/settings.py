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
    db_mode: str = "postgresql"

    @property
    def is_sqlite_dev(self) -> bool:
        return self.db_mode == "sqlite-dev"

    @classmethod
    def from_env(cls) -> "Settings":
        load_local_env()
        db_mode = os.getenv("DB_MODE", "postgresql").strip() or "postgresql"
        database_url = os.getenv("DATABASE_URL", "").strip()
        storage_root = os.getenv("STORAGE_ROOT", "").strip()
        if db_mode not in {"postgresql", "sqlite-dev"}:
            raise ConfigurationError("DB_MODE must be either 'postgresql' or 'sqlite-dev'")
        missing = []
        if not database_url:
            missing.append("DATABASE_URL")
        if not storage_root:
            missing.append("STORAGE_ROOT")
        if missing:
            raise ConfigurationError(
                "Missing required environment variable(s): " + ", ".join(missing)
            )
        if db_mode == "postgresql" and not database_url.startswith("postgresql+psycopg://"):
            raise ConfigurationError(
                "DATABASE_URL must use PostgreSQL with psycopg 3, for example: "
                "postgresql+psycopg://user:password@host:5432/slopeforge"
            )
        if db_mode == "sqlite-dev" and database_url != "sqlite:///slopeforge_dev.db":
            raise ConfigurationError(
                "sqlite-dev mode must use DATABASE_URL=sqlite:///slopeforge_dev.db. "
                "This mode is only for local development and not for production data."
            )
        return cls(database_url=database_url, storage_root=Path(storage_root).expanduser(), db_mode=db_mode)


def safe_database_location(database_url: str) -> str:
    """Return DATABASE_URL location without password for UI messages."""
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        return str(url.database)
    host = url.host or "localhost"
    port = f":{url.port}" if url.port else ""
    database = url.database or ""
    username = f"{url.username}@" if url.username else ""
    return f"{username}{host}{port}/{database}"
