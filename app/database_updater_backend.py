from __future__ import annotations

from pathlib import Path

from application.services.database_upgrade import (
    BackupRecord,
    DatabaseCompatibility,
    DatabaseInspection,
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
