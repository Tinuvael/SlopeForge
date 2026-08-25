from __future__ import annotations

from pathlib import Path

import pytest

import database.startup as startup
from database.connection import DatabaseConnectionError
from database.settings import Settings


class FakeEngine:
    def __init__(self):
        self.dispose_calls = 0

    def dispose(self):
        self.dispose_calls += 1


def _settings() -> Settings:
    return Settings(
        "postgresql+psycopg://slopeforge:secret@db.example:5432/slopeforge",
        Path("/tmp/storage"),
    )


def test_startup_disposes_engine_when_connection_check_fails(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(startup, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(
        startup,
        "check_connection",
        lambda _engine: (_ for _ in ()).throw(DatabaseConnectionError("connection failed")),
    )

    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime(_settings())

    assert caught.value.reason == "connection_error"
    assert engine.dispose_calls == 1


def test_startup_disposes_engine_when_schema_validation_fails(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(startup, "create_database_engine", lambda _settings: engine)
    monkeypatch.setattr(startup, "check_connection", lambda _engine: None)
    monkeypatch.setattr(startup, "_initialize_empty_database", lambda *_args: None)
    monkeypatch.setattr(
        startup,
        "_verify_alembic_revision",
        lambda *_args: (_ for _ in ()).throw(
            startup.StartupError(
                "older schema",
                reason="database_upgrade_required",
            )
        ),
    )

    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime(_settings())

    assert caught.value.reason == "database_upgrade_required"
    assert engine.dispose_calls == 1
