from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import configure_mappers
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from .base import Base
from . import assessment_models  # noqa: F401  Ensure Assessment tables are validated.
from .connection import (DatabaseConnectionError, check_connection,
                         create_database_engine, create_session_factory)
from .models import User  # noqa: F401
from .settings import ConfigurationError, Settings, safe_database_location


class StartupError(RuntimeError):
    def __init__(self, message: str, server: str | None = None):
        super().__init__(message)
        self.server = server


def _expected_alembic_head() -> str:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        rendered = ", ".join(heads) if heads else "none"
        raise StartupError(
            f"The application migration graph must have exactly one head; found: {rendered}."
        )
    return heads[0]


def _database_alembic_heads(engine) -> tuple[str, ...]:
    with engine.connect() as connection:
        return tuple(MigrationContext.configure(connection).get_current_heads())


def _verify_alembic_revision(engine, server: str | None) -> None:
    required = _expected_alembic_head()
    try:
        current_heads = _database_alembic_heads(engine)
    except SQLAlchemyError as exc:
        raise StartupError(
            f"Could not read the database Alembic revision. Required revision: {required}. "
            "Run migrations: python -m database.cli migrate",
            server,
        ) from exc
    current = ", ".join(current_heads) if current_heads else "missing"
    if current_heads != (required,):
        raise StartupError(
            f"Database revision: {current}. Required revision: {required}. "
            "Run migrations: python -m database.cli migrate",
            server,
        )


def initialize_database_runtime():
    try:
        settings = Settings.from_env()
        engine = create_database_engine(settings)
        check_connection(engine)
        server = safe_database_location(settings.database_url)
        _verify_alembic_revision(engine, server)
        configure_mappers()
        existing = set(inspect(engine).get_table_names())
        required = set(Base.metadata.tables)
        missing = sorted(required - existing)
        if missing:
            raise StartupError(
                "Required tables were not found in the database: " + ", ".join(missing[:8]) + ("..." if len(missing) > 8 else ""),
                server,
            )
        return settings, engine, create_session_factory(engine)
    except ConfigurationError as exc:
        raise StartupError(str(exc)) from exc
    except DatabaseConnectionError as exc:
        server = None
        try:
            server = safe_database_location(Settings.from_env().database_url)
        except Exception:
            server = None
        raise StartupError(str(exc), server) from exc
    except SQLAlchemyError as exc:
        server = None
        try:
            server = safe_database_location(Settings.from_env().database_url)
        except Exception:
            server = None
        raise StartupError("Could not connect to the database or verify tables.", server) from exc
