from pathlib import Path

from alembic.util.exc import CommandError

import database.cli as cli
from database.settings import Settings


def _settings(name):
    return Settings(
        f"postgresql+psycopg://owner:secret@db.example:5432/{name}",
        Path("/tmp/storage"),
    )


def test_migrate_unknown_revision_is_controlled(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.command,
        "upgrade",
        lambda *_: (_ for _ in ()).throw(
            CommandError("Can't locate revision identified by '20260809_0008'")
        ),
    )
    assert cli.migrate() == 1
    error = capsys.readouterr().err
    assert "cannot be migrated" in error
    assert "reset-dev-db" in error
    assert "Traceback" not in error


def test_reset_refuses_protected_databases(monkeypatch, capsys):
    for name in ("postgres", "template0", "template1"):
        monkeypatch.setattr(cli, "_runtime_settings", lambda name=name: _settings(name))
        assert cli.reset_dev_db(confirmation_reader=lambda _: name) == 1
    assert capsys.readouterr().err.count("Refusing to reset protected") == 3


def test_reset_wrong_confirmation_aborts_before_connection(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_runtime_settings", lambda: _settings("slopeforge"))
    monkeypatch.setattr(
        cli,
        "create_engine",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not connect")),
    )
    assert cli.reset_dev_db(confirmation_reader=lambda _: "wrong") == 1
    assert "aborted" in capsys.readouterr().err


def test_reset_exact_confirmation_recreates_and_migrates(monkeypatch):
    calls = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, statement, params=None):
            calls.append((str(statement), params))

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            calls.append(("dispose", None))

    monkeypatch.setattr(cli, "_runtime_settings", lambda: _settings("slopeforge"))
    monkeypatch.setattr(cli, "create_engine", lambda url, **kwargs: Engine())
    monkeypatch.setattr(
        cli.command,
        "upgrade",
        lambda config, target: calls.append(("upgrade", target)),
    )
    assert cli.reset_dev_db(confirmation_reader=lambda _: "slopeforge") == 0
    sql = "\n".join(item[0] for item in calls)
    assert "pg_terminate_backend" in sql
    assert 'DROP DATABASE IF EXISTS "slopeforge"' in sql
    assert 'CREATE DATABASE "slopeforge"' in sql
    assert ("upgrade", "head") in calls
