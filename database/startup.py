from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import configure_mappers
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError
from alembic.util.exc import CommandError

from .base import Base
from . import assessment_models  # noqa: F401  Ensure Assessment tables are validated.
from . import project_surface_models  # noqa: F401  Ensure Project surface metadata is validated.
from . import drillhole_models  # noqa: F401  Ensure BlastEvent drillhole tables are validated.
from .connection import (DatabaseConnectionError, check_connection,
                         create_database_engine, create_session_factory)
from .models import User  # noqa: F401
from .migrations import upgrade_to_head
from .settings import ConfigurationError, Settings, safe_database_location


PRE_1_0_DEVELOPMENT_REVISIONS = frozenset({
    "0001_mvp_baseline",
    "0002_project_surface_datasets",
    "0003_drillhole_datasets",
})


class StartupError(RuntimeError):
    def __init__(self, message: str, server: str | None = None, *,
                 reason: str = "database_error", actions: tuple[str, ...] = ()):
        super().__init__(message)
        self.server = server
        self.reason = reason
        self.actions = actions

    def presentation(self) -> str:
        details = [str(self)]
        if self.server:
            details.append(f"Server/database: {self.server}")
        details.extend(self.actions)
        return "\n\n".join(details)


def _alembic_script() -> ScriptDirectory:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return ScriptDirectory.from_config(config)


def _expected_alembic_head() -> str:
    heads = _alembic_script().get_heads()
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
            "Could not read the database schema version.",
            server, reason="database_revision_unreadable",
        ) from exc

    if current_heads == (required,):
        return

    if len(current_heads) != 1:
        raise StartupError(
            "The selected database has an incompatible schema state.",
            server, reason="database_version_incompatible",
        )

    current = current_heads[0]
    if current in PRE_1_0_DEVELOPMENT_REVISIONS:
        raise StartupError(
            "The selected database uses an older SlopeForge schema.",
            server, reason="database_upgrade_required",
        )

    script = _alembic_script()
    try:
        known_revision = script.get_revision(current)
    except (CommandError, ResolutionError):
        known_revision = None

    if known_revision is not None:
        # With the single-head migration policy, a recognized non-head revision is
        # an older schema that can only be opened after the database is upgraded.
        raise StartupError(
            "The selected database uses an older SlopeForge schema.",
            server, reason="database_upgrade_required",
        )

    # An installed application cannot inspect a migration that was introduced by
    # a later release. Treat an unknown post-1.0 revision as requiring a newer
    # SlopeForge build rather than attempting to modify an unfamiliar schema.
    raise StartupError(
        "The selected database requires a newer or otherwise unsupported SlopeForge schema.",
        server, reason="application_upgrade_required",
    )


def _initialize_empty_database(engine, settings: Settings, server: str | None) -> None:
    """Apply the migration graph only when no Alembic head and no user tables exist."""
    if _database_alembic_heads(engine):
        return
    existing = set(inspect(engine).get_table_names())
    if existing:
        raise StartupError(
            "The selected database contains data but has no recognized SlopeForge schema version.",
            server, reason="database_version_incompatible",
        )
    upgrade_to_head(settings)


def initialize_database_runtime(settings: Settings | None = None):
    runtime_settings: Settings | None = settings
    try:
        runtime_settings = runtime_settings or Settings.from_env()
        engine = create_database_engine(runtime_settings)
        check_connection(engine)
        server = safe_database_location(runtime_settings.database_url)
        _initialize_empty_database(engine, runtime_settings, server)
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
        return runtime_settings, engine, create_session_factory(engine)
    except ConfigurationError as exc:
        raise StartupError(str(exc), reason="configuration_error",
                           actions=("Configure the PostgreSQL server and file storage in SlopeForge Settings.",)) from exc
    except DatabaseConnectionError as exc:
        server = safe_database_location(runtime_settings.database_url) if runtime_settings else None
        raise StartupError(str(exc), server, reason="connection_error") from exc
    except SQLAlchemyError as exc:
        server = safe_database_location(runtime_settings.database_url) if runtime_settings else None
        raise StartupError("Could not connect to the database or verify tables.", server,
                           reason="database_error") from exc
