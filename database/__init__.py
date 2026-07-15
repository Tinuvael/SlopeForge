from __future__ import annotations

from .database import Database

_db: Database | None = None


def get_legacy_database() -> Database:
    """Return the existing SQLite-backed UI database lazily.

    The current desktop UI imports ``db`` from this package. Lazy creation keeps
    that interface working while allowing PostgreSQL/Alembic modules to import
    ``database.*`` without opening the legacy SQLite file as a side effect.
    """
    global _db
    if _db is None:
        _db = Database()
    return _db


def __getattr__(name: str):
    if name == "db":
        return get_legacy_database()
    raise AttributeError(name)
