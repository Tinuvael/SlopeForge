from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set; PostgreSQL Alembic integration test skipped")
def test_alembic_upgrade_downgrade_upgrade_cycle_on_postgresql(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    command = pytest.importorskip("alembic.command", reason="Alembic package is not installed", exc_type=ImportError)
    config_module = pytest.importorskip("alembic.config", reason="Alembic package is not installed", exc_type=ImportError)
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    config = config_module.Config("alembic.ini")

    command.upgrade(config, "head")
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.begin() as connection:
        mine_id = connection.scalar(text(
            "INSERT INTO mines (name) VALUES ('downgrade domains') RETURNING id"))
        site_id = connection.scalar(text(
            "INSERT INTO sites (mine_id, name) VALUES (:mine, 'Pit') RETURNING id"),
            {"mine": mine_id})
        first = connection.scalar(text(
            "INSERT INTO domains (site_id, name) VALUES (:site, 'North') RETURNING id"),
            {"site": site_id})
        second = connection.scalar(text(
            "INSERT INTO domains (site_id, name) VALUES (:site, 'South') RETURNING id"),
            {"site": site_id})
        connection.execute(text(
            "INSERT INTO assessment_workspaces (domain_id) VALUES (:first), (:second)"),
            {"first": first, "second": second})
    command.downgrade(config, "20260804_0005")
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM assessment_workspaces WHERE site_id=:site"),
            {"site": site_id}) == 1
    engine.dispose()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
