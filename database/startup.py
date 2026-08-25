from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from .connection import (
    DatabaseConnectionError,
    check_connection,
    create_database_engine,
    create_session_factory,
)
from .migrations import upgrade_to_head
from .schema_compatibility import (
    SchemaCompatibilityState,
    classify_schema_compatibility,
    database_alembic_heads,
    expected_alembic_head,
    known_alembic_revisions,
    missing_required_tables,
)
from .settings import ConfigurationError, Settings, safe_database_location


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


def _expected_alembic_head() -> str:
    """Compatibility wrapper kept for startup tests/callers."""
    try:
        return expected_alembic_head()
    except RuntimeError as exc:
        raise StartupError(str(exc)) from exc


def _database_alembic_heads(engine) -> tuple[str, ...]:
    """Compatibility wrapper kept for startup tests/callers."""
    return database_alembic_heads(engine)


def _verify_alembic_revision(engine, server: str | None) -> None:
    required = _expected_alembic_head()
    try:
        current_heads = _database_alembic_heads(engine)
    except SQLAlchemyError as exc:
        raise StartupError(
            "Could not read the database schema version.",
            server,
            reason="database_revision_unreadable",
        ) from exc

    report = classify_schema_compatibility(
        current_heads,
        required,
        known_alembic_revisions(),
    )
    if report.state == SchemaCompatibilityState.UP_TO_DATE:
        return
    if report.state == SchemaCompatibilityState.NEWER_THAN_RELEASE:
        raise StartupError(
            "The selected database requires a newer version of SlopeForge.",
            server,
            reason="application_upgrade_required",
        )
    if report.state == SchemaCompatibilityState.UPGRADE_REQUIRED:
        raise StartupError(
            "The selected database uses an older SlopeForge schema.",
            server,
            reason="database_upgrade_required",
        )
    raise StartupError(
        "The selected database has an incompatible schema version.",
        server,
        reason="database_version_incompatible",
    )


def _initialize_empty_database(engine, settings: Settings, server: str | None) -> None:
    """Apply the migration graph only when no Alembic head and no user tables exist."""
    if _database_alembic_heads(engine):
        return
    existing = set(inspect(engine).get_table_names())
    if existing:
        raise StartupError(
            "The selected database contains data but has no recognized SlopeForge schema version.",
            server,
            reason="database_version_incompatible",
        )
    upgrade_to_head(settings)


def _dispose_failed_engine(engine) -> None:
    """Release a partially initialized runtime without masking its startup error."""
    dispose = getattr(engine, "dispose", None)
    if not callable(dispose):
        return
    try:
        dispose()
    except Exception:
        # The original startup failure is more actionable than a secondary pool
        # teardown error, and SQLAlchemy Engine.dispose() is normally non-raising.
        pass


def initialize_database_runtime(settings: Settings | None = None):
    runtime_settings: Settings | None = settings
    engine = None
    runtime_ready = False
    try:
        runtime_settings = runtime_settings or Settings.from_env()
        engine = create_database_engine(runtime_settings)
        check_connection(engine)
        server = safe_database_location(runtime_settings.database_url)
        _initialize_empty_database(engine, runtime_settings, server)
        _verify_alembic_revision(engine, server)
        missing = list(missing_required_tables(engine))
        if missing:
            raise StartupError(
                "Required tables were not found in the database: "
                + ", ".join(missing[:8])
                + ("..." if len(missing) > 8 else ""),
                server,
            )
        session_factory = create_session_factory(engine)
        runtime_ready = True
        return runtime_settings, engine, session_factory
    except ConfigurationError as exc:
        raise StartupError(
            str(exc),
            reason="configuration_error",
            actions=(
                "Configure the PostgreSQL server and file storage in SlopeForge Settings.",
            ),
        ) from exc
    except DatabaseConnectionError as exc:
        server = (
            safe_database_location(runtime_settings.database_url)
            if runtime_settings
            else None
        )
        raise StartupError(str(exc), server, reason="connection_error") from exc
    except SQLAlchemyError as exc:
        server = (
            safe_database_location(runtime_settings.database_url)
            if runtime_settings
            else None
        )
        raise StartupError(
            "Could not connect to the database or verify tables.",
            server,
            reason="database_error",
        ) from exc
    finally:
        if engine is not None and not runtime_ready:
            _dispose_failed_engine(engine)
