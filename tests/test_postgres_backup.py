from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from database.settings import Settings
from infrastructure.db.postgres_backup import (
    PostgresBackupError,
    backup_filename,
    create_postgres_backup,
)


FIXED_TIME = datetime(2026, 8, 26, 1, 2, 3, tzinfo=timezone.utc)


def _settings(password: str = "top-secret") -> Settings:
    return Settings.from_values(
        f"postgresql+psycopg://admin:{password}@db.example:5433/slopeforge_test?sslmode=require",
        None,
        database_only=True,
    )


def test_backup_filename_is_deterministic_and_safe() -> None:
    assert backup_filename(_settings(), "2/dev", FIXED_TIME) == (
        "SlopeForge_slopeforge_test_2026-08-26_01-02-03_2_dev.dump"
    )


def test_pg_dump_password_is_environment_only_and_non_empty_output_is_required(tmp_path: Path) -> None:
    captured = {}

    def runner(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        target = Path(command[command.index("--file") + 1])
        target.write_bytes(b"valid-custom-format-backup")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    artifact = create_postgres_backup(
        _settings(),
        tmp_path,
        revision="1",
        pg_dump_executable="pg_dump-test",
        now=lambda: FIXED_TIME,
        runner=runner,
    )

    assert artifact.path.exists()
    assert artifact.size_bytes > 0
    assert "top-secret" not in " ".join(captured["command"])
    assert captured["env"]["PGPASSWORD"] == "top-secret"
    assert captured["env"]["PGHOST"] == "db.example"
    assert captured["env"]["PGPORT"] == "5433"
    assert captured["env"]["PGDATABASE"] == "slopeforge_test"
    assert captured["env"]["PGUSER"] == "admin"
    assert captured["env"]["PGSSLMODE"] == "require"


def test_failed_pg_dump_removes_partial_file_and_redacts_password(tmp_path: Path) -> None:
    password = "s/ecret:word"

    def runner(command, **_kwargs):
        target = Path(command[command.index("--file") + 1])
        target.write_bytes(b"partial")
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr=f"authentication failed for {password}",
        )

    with pytest.raises(PostgresBackupError) as caught:
        create_postgres_backup(
            _settings(password),
            tmp_path,
            revision="1",
            pg_dump_executable="pg_dump-test",
            now=lambda: FIXED_TIME,
            runner=runner,
        )

    assert password not in str(caught.value)
    assert "<redacted>" in str(caught.value)
    assert list(tmp_path.glob("*.dump")) == []


def test_success_exit_with_empty_output_is_rejected_and_cleaned(tmp_path: Path) -> None:
    def runner(command, **_kwargs):
        target = Path(command[command.index("--file") + 1])
        target.touch()
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with pytest.raises(PostgresBackupError, match="empty backup file"):
        create_postgres_backup(
            _settings(),
            tmp_path,
            revision="1",
            pg_dump_executable="pg_dump-test",
            now=lambda: FIXED_TIME,
            runner=runner,
        )

    assert list(tmp_path.glob("*.dump")) == []


def test_existing_backup_is_never_overwritten(tmp_path: Path) -> None:
    target = tmp_path / backup_filename(_settings(), "1", FIXED_TIME)
    target.write_bytes(b"existing")

    with pytest.raises(PostgresBackupError, match="will not be overwritten"):
        create_postgres_backup(
            _settings(),
            tmp_path,
            revision="1",
            now=lambda: FIXED_TIME,
        )

    assert target.read_bytes() == b"existing"
