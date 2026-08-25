from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import text

from application.services.database_upgrade import (
    BackupRecord,
    DatabaseCompatibility,
    DatabaseInspection,
    DatabaseUpgradeError,
    DatabaseUpgradeService,
)
from database.connection import check_connection, create_database_engine
from database.migrations import upgrade_to_head
from database.schema_compatibility import (
    SchemaCompatibilityState,
    inspect_schema_compatibility,
    missing_required_tables,
)
from database.settings import Settings
from infrastructure.db.postgres_backup import create_postgres_backup


# Stable process-independent lock key for SlopeForge schema maintenance.
_UPDATER_ADVISORY_LOCK_KEY = 0x534C4F5045464F52  # ASCII-ish: SLOPEFOR

_COMPATIBILITY_MAP = {
    SchemaCompatibilityState.UP_TO_DATE: DatabaseCompatibility.UP_TO_DATE,
    SchemaCompatibilityState.UPGRADE_REQUIRED: DatabaseCompatibility.UPGRADE_REQUIRED,
    SchemaCompatibilityState.NEWER_THAN_RELEASE: DatabaseCompatibility.NEWER_THAN_RELEASE,
    SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED: DatabaseCompatibility.UNKNOWN_OR_UNSUPPORTED,
}


class RuntimeMigrationGateway:
    def __init__(self, settings: Settings):
        self.settings = settings

    def inspect_database(self) -> DatabaseInspection:
        engine = create_database_engine(self.settings)
        try:
            check_connection(engine)
            report = inspect_schema_compatibility(engine)
            missing = (
                missing_required_tables(engine)
                if report.state == SchemaCompatibilityState.UP_TO_DATE
                else ()
            )
            return DatabaseInspection(
                current_heads=report.current_heads,
                required_revision=report.required_head,
                compatibility=_COMPATIBILITY_MAP[report.state],
                missing_tables=tuple(missing),
            )
        finally:
            engine.dispose()

    @contextmanager
    def upgrade_guard(self):
        """Hold a session-level PostgreSQL advisory lock for the whole workflow."""
        engine = create_database_engine(self.settings)
        connection = None
        acquired = False
        try:
            connection = engine.connect()
            acquired = bool(
                connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": _UPDATER_ADVISORY_LOCK_KEY},
                )
            )
            if not acquired:
                raise DatabaseUpgradeError(
                    "Another SlopeForge updater is already maintaining this database."
                )
            yield
        finally:
            if connection is not None:
                if acquired:
                    try:
                        connection.execute(
                            text("SELECT pg_advisory_unlock(:key)"),
                            {"key": _UPDATER_ADVISORY_LOCK_KEY},
                        )
                    except Exception:
                        # Never mask the workflow error with a secondary unlock error;
                        # closing the PostgreSQL session releases advisory locks anyway.
                        pass
                connection.close()
            engine.dispose()

    def upgrade_to_head(self) -> None:
        upgrade_to_head(self.settings)


class RuntimeBackupGateway:
    def __init__(self, settings: Settings, *, pg_dump_executable: str = "pg_dump"):
        self.settings = settings
        self.pg_dump_executable = pg_dump_executable

    def create_backup(
        self,
        backup_directory: str | Path,
        revision: str | None,
    ) -> BackupRecord:
        artifact = create_postgres_backup(
            self.settings,
            backup_directory,
            revision=revision,
            pg_dump_executable=self.pg_dump_executable,
        )
        return BackupRecord(path=artifact.path, size_bytes=artifact.size_bytes)


def create_database_upgrade_service(
    settings: Settings,
    *,
    pg_dump_executable: str = "pg_dump",
) -> DatabaseUpgradeService:
    return DatabaseUpgradeService(
        RuntimeMigrationGateway(settings),
        RuntimeBackupGateway(settings, pg_dump_executable=pg_dump_executable),
    )
