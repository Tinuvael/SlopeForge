from pathlib import Path

import pytest

from application.services.database_upgrade import (
    BackupRecord,
    DatabaseCompatibility,
    DatabaseInspection,
    DatabaseUpgradeError,
    DatabaseUpgradeService,
    UpgradeAlreadyRunningError,
)


def _inspection(
    state: DatabaseCompatibility,
    current: str = "1",
    required: str = "2",
    missing=(),
) -> DatabaseInspection:
    return DatabaseInspection(
        current_heads=(current,),
        required_revision=required,
        compatibility=state,
        missing_tables=tuple(missing),
    )


class FakeMigration:
    def __init__(self, inspections, *, upgrade_error=None):
        self.inspections = list(inspections)
        self.upgrade_error = upgrade_error
        self.upgrade_calls = 0

    def inspect_database(self):
        if len(self.inspections) > 1:
            return self.inspections.pop(0)
        return self.inspections[0]

    def upgrade_to_head(self):
        self.upgrade_calls += 1
        if self.upgrade_error:
            raise self.upgrade_error


class FakeBackups:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def create_backup(self, backup_directory, revision):
        self.calls.append((Path(backup_directory), revision))
        if self.error:
            raise self.error
        return BackupRecord(Path(backup_directory) / "before.dump", 123)


def test_backup_failure_prevents_alembic_upgrade(tmp_path: Path) -> None:
    migration = FakeMigration([_inspection(DatabaseCompatibility.UPGRADE_REQUIRED)])
    backups = FakeBackups(error=RuntimeError("backup failed"))
    service = DatabaseUpgradeService(migration, backups)

    with pytest.raises(RuntimeError, match="backup failed"):
        service.backup_and_upgrade(tmp_path)

    assert migration.upgrade_calls == 0
    assert len(backups.calls) == 1


def test_unknown_or_newer_schema_is_refused_before_backup(tmp_path: Path) -> None:
    for state in (
        DatabaseCompatibility.UNKNOWN_OR_UNSUPPORTED,
        DatabaseCompatibility.NEWER_THAN_RELEASE,
    ):
        migration = FakeMigration([_inspection(state)])
        backups = FakeBackups()
        service = DatabaseUpgradeService(migration, backups)

        with pytest.raises(DatabaseUpgradeError):
            service.backup_and_upgrade(tmp_path)

        assert backups.calls == []
        assert migration.upgrade_calls == 0


def test_success_requires_exact_post_upgrade_schema_and_required_tables(tmp_path: Path) -> None:
    before = _inspection(DatabaseCompatibility.UPGRADE_REQUIRED, current="1", required="2")
    after = _inspection(DatabaseCompatibility.UP_TO_DATE, current="2", required="2")
    migration = FakeMigration([before, after])
    backups = FakeBackups()

    result = DatabaseUpgradeService(migration, backups).backup_and_upgrade(tmp_path)

    assert result.before == before
    assert result.after == after
    assert result.backup.path == tmp_path / "before.dump"
    assert migration.upgrade_calls == 1


def test_post_upgrade_verification_failure_preserves_backup_path(tmp_path: Path) -> None:
    before = _inspection(DatabaseCompatibility.UPGRADE_REQUIRED)
    after = _inspection(
        DatabaseCompatibility.UP_TO_DATE,
        current="2",
        required="2",
        missing=("users",),
    )
    migration = FakeMigration([before, after])
    backups = FakeBackups()

    with pytest.raises(DatabaseUpgradeError) as caught:
        DatabaseUpgradeService(migration, backups).backup_and_upgrade(tmp_path)

    assert caught.value.backup_path == tmp_path / "before.dump"
    assert migration.upgrade_calls == 1


def test_migration_failure_reports_preserved_backup(tmp_path: Path) -> None:
    migration = FakeMigration(
        [_inspection(DatabaseCompatibility.UPGRADE_REQUIRED)],
        upgrade_error=RuntimeError("alembic failed"),
    )
    backups = FakeBackups()

    with pytest.raises(DatabaseUpgradeError) as caught:
        DatabaseUpgradeService(migration, backups).backup_and_upgrade(tmp_path)

    assert caught.value.backup_path == tmp_path / "before.dump"
    assert migration.upgrade_calls == 1


def test_duplicate_upgrade_in_same_process_is_refused(tmp_path: Path) -> None:
    service = DatabaseUpgradeService(
        FakeMigration([_inspection(DatabaseCompatibility.UPGRADE_REQUIRED)]),
        FakeBackups(),
    )
    assert service._upgrade_lock.acquire(blocking=False)
    try:
        with pytest.raises(UpgradeAlreadyRunningError):
            service.backup_and_upgrade(tmp_path)
    finally:
        service._upgrade_lock.release()
