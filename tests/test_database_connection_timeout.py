from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

import database.connection as connection
from database.settings import Settings


def settings(url="postgresql+psycopg://user:secret@db.example/slopeforge"):
    return Settings(url, Path("/tmp/storage"))


def test_canonical_engine_uses_five_second_connect_timeout(monkeypatch):
    captured = {}
    monkeypatch.setattr(connection, "create_engine",
                        lambda url, **kwargs: captured.update(url=url, **kwargs) or object())

    connection.create_database_engine(settings())

    assert captured["connect_args"] == {"connect_timeout": 5}
    assert captured["pool_pre_ping"] is True
    assert "secret" not in repr(captured["connect_args"])


def test_explicit_url_connect_timeout_is_not_overridden(monkeypatch):
    captured = {}
    monkeypatch.setattr(connection, "create_engine",
                        lambda url, **kwargs: captured.update(url=url, **kwargs) or object())

    connection.create_database_engine(settings(
        "postgresql+psycopg://user:secret@db.example/slopeforge?connect_timeout=12"))

    assert captured["connect_args"] == {}
    assert "connect_timeout=12" in captured["url"]


def test_operational_connection_failure_keeps_user_facing_postgresql_guidance():
    class Engine:
        def connect(self):
            raise OperationalError("connect", {}, RuntimeError("timed out"))

    with pytest.raises(connection.DatabaseConnectionError) as caught:
        connection.check_connection(Engine())

    message = str(caught.value)
    assert "Cannot connect to PostgreSQL" in message
    assert "server address" in message
    assert "network" in message
    assert "credentials" in message
    assert "PostgreSQL administrator" in message
    assert "DATABASE_URL" not in message
    assert "python -m" not in message
    assert "prepare-db" not in message
