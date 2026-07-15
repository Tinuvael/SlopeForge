from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set; PostgreSQL Alembic integration test skipped")
def test_alembic_upgrade_downgrade_upgrade_cycle_on_postgresql(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    command = pytest.importorskip("alembic.command", reason="Alembic package is not installed", exc_type=ImportError)
    config_module = pytest.importorskip("alembic.config", reason="Alembic package is not installed", exc_type=ImportError)
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    config = config_module.Config("alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
