from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Protocol


class DatabaseCompatibility(str, Enum):
    UP_TO_DATE = "up_to_date"
    UPGRADE_REQUIRED = "upgrade_required"
    NEWER_THAN_RELEASE = "newer_than_release"
    UNKNOWN_OR_UNSUPPORTED = "unknown_or_unsupported"


@dataclass(frozen=True)
class DatabaseInspection:
    current_heads: tuple[str, ...]
    required_revision: str
    compatibility: DatabaseCompatibility
    missing_tables: tuple[str, ...] = ()

    @property
    def current_revision(self) -> str | None:
        return self.current_heads[0] if len(self.current_heads) == 1 else None

    @property
    def verified(self) -> bool:
        return (
            self.compatibility == DatabaseCompatibility.UP_TO_DATE
            and not self.missing_tables
        )


@dataclass(frozen=True)
class BackupRecord:
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class UpgradeResult:
    before: DatabaseInspection
    after: DatabaseInspection
    backup: BackupRecord


class MigrationGateway(Protocol):
    def inspect_database(self) -> DatabaseInspection: ...
    def upgrade_to_head(self) -> None: ...


class BackupGateway(Protocol):
    def create_backup(
        self,
        backup_directory: str | Path,
        revision: str | None,
    ) -> BackupRecord: ...


class DatabaseUpgradeError(RuntimeError):
    def __init__(self, message: str, *, backup_path: Path | None = None):
        super().__init__(message)
        self.backup_path = backup_path


class UpgradeAlreadyRunningError(DatabaseUpgradeError):
    pass


class DatabaseUpgradeService:
    """Sequence inspection, verified backup, migration and post-upgrade verification."""

    def __init__(self, migration: MigrationGateway, backups: BackupGateway):
        self._migration = migration
        self._backups = backups
        self._upgrade_lock = Lock()

    def inspect_database(self) -> DatabaseInspection:
        return self._migration.inspect_database()

    def verify_database(self) -> DatabaseInspection:
        return self._migration.inspect_database()

    def create_backup(self, backup_directory: str | Path) -> BackupRecord:
        inspection = self._migration.inspect_database()
        return self._backups.create_backup(
            backup_directory,
            inspection.current_revision,
        )

    def _database_guard(self):
        guard = getattr(self._migration, "upgrade_guard", None)
        return guard() if callable(guard) else nullcontext()

    def backup_and_upgrade(self, backup_directory: str | Path) -> UpgradeResult:
        if not self._upgrade_lock.acquire(blocking=False):
            raise UpgradeAlreadyRunningError(
                "A database upgrade is already running in this updater process."
            )
        try:
            # Runtime gateways use this guard for a PostgreSQL advisory lock so
            # two updater processes cannot migrate the same database at once.
            with self._database_guard():
                before = self._migration.inspect_database()
                if before.compatibility == DatabaseCompatibility.UP_TO_DATE:
                    raise DatabaseUpgradeError(
                        "The database is already at the schema revision required by this release."
                    )
                if before.compatibility == DatabaseCompatibility.NEWER_THAN_RELEASE:
                    raise DatabaseUpgradeError(
                        "The database was created by a newer SlopeForge release and cannot be downgraded."
                    )
                if before.compatibility == DatabaseCompatibility.UNKNOWN_OR_UNSUPPORTED:
                    raise DatabaseUpgradeError(
                        "The database schema revision is unknown or unsupported; automatic migration is refused."
                    )

                # This must complete successfully before any Alembic mutation occurs.
                backup = self._backups.create_backup(
                    backup_directory,
                    before.current_revision,
                )
                try:
                    self._migration.upgrade_to_head()
                except Exception as exc:
                    raise DatabaseUpgradeError(
                        "Database migration failed. The pre-upgrade backup was preserved.",
                        backup_path=backup.path,
                    ) from exc

                try:
                    after = self._migration.inspect_database()
                except Exception as exc:
                    raise DatabaseUpgradeError(
                        "Database migration completed but post-upgrade verification failed. "
                        "The pre-upgrade backup was preserved.",
                        backup_path=backup.path,
                    ) from exc
                if not after.verified:
                    raise DatabaseUpgradeError(
                        "Database migration did not produce the exact schema required by this release. "
                        "The pre-upgrade backup was preserved.",
                        backup_path=backup.path,
                    )
                return UpgradeResult(before=before, after=after, backup=backup)
        finally:
            self._upgrade_lock.release()
