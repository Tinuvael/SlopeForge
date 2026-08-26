from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from app.database_updater_backend import RuntimeMigrationGateway
from application.services.database_upgrade import DatabaseCompatibility, DatabaseUpgradeError
from database.settings import Settings
from infrastructure.db.postgres_backup import create_postgres_backup


pytestmark = pytest.mark.postgres


def _settings() -> Settings:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return Settings.from_values(url, None, database_only=True)


def test_updater_inspection_reports_current_bundled_schema() -> None:
    inspection = RuntimeMigrationGateway(_settings()).inspect_database()
    assert inspection.compatibility == DatabaseCompatibility.UP_TO_DATE
    assert inspection.current_heads == (inspection.required_revision,)
    assert inspection.missing_tables == ()
    assert inspection.verified is True


def test_advisory_lock_refuses_a_second_maintenance_session() -> None:
    first = RuntimeMigrationGateway(_settings())
    second = RuntimeMigrationGateway(_settings())
    with first.upgrade_guard():
        with pytest.raises(DatabaseUpgradeError, match="already maintaining"):
            with second.upgrade_guard():
                pass


@pytest.mark.skipif(shutil.which("pg_dump") is None, reason="pg_dump is not installed")
def test_pg_dump_creates_a_verified_non_empty_backup(tmp_path: Path) -> None:
    settings = _settings()
    inspection = RuntimeMigrationGateway(settings).inspect_database()
    artifact = create_postgres_backup(
        settings,
        tmp_path,
        revision=inspection.current_revision,
        pg_dump_executable=shutil.which("pg_dump") or "pg_dump",
    )
    assert artifact.path.is_file()
    assert artifact.path.suffix == ".dump"
    assert artifact.size_bytes == artifact.path.stat().st_size
    assert artifact.size_bytes > 0
