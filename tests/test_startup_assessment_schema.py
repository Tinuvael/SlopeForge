from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import database.startup as startup
from database.settings import Settings


class FakeInspector:
    def __init__(self, tables=()): self.tables = tables
    def get_table_names(self): return list(self.tables)


def test_expected_alembic_head_resolves_real_repository_graph():
    """Exercise the production path/config rather than a mocked head helper."""
    repository_heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    assert repository_heads == ["0002_derive_blast_workflow_status"]
    assert startup._expected_alembic_head() == repository_heads[0]


def arrange_startup(monkeypatch, *, revision="0001_mvp_baseline", tables=None):
    settings = Settings("postgresql+psycopg://u:secret@db.example:5432/slopeforge", Path("/tmp/storage"))
    engine = object()
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: engine)
    monkeypatch.setattr(startup, "create_session_factory", lambda value: "sessions")
    monkeypatch.setattr(startup, "check_connection", lambda value: None)
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: "0001_mvp_baseline")
    monkeypatch.setattr(startup, "_database_alembic_heads", lambda value: (() if revision is None else (revision,)))
    monkeypatch.setattr(startup, "configure_mappers", lambda: None)
    monkeypatch.setattr(startup, "inspect", lambda value: FakeInspector(
        startup.Base.metadata.tables if tables is None else tables))
    return settings, engine


def test_startup_requires_assessment_tables_and_does_not_run_migrations(monkeypatch):
    arrange_startup(monkeypatch, tables=())

    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()

    message = str(caught.value)
    assert "assessment_" in message or "blast_event_" in message
    assert "assessment_workspaces" not in startup.Base.metadata.tables
    assert "blast_events" in startup.Base.metadata.tables
    assert "assessment_entity_attachments" in startup.Base.metadata.tables


def test_startup_accepts_database_at_the_single_current_head(monkeypatch):
    settings, engine = arrange_startup(monkeypatch)
    assert startup.initialize_database_runtime() == (settings, engine, "sessions")


def test_startup_rejects_stale_revision_even_when_all_tables_exist(monkeypatch):
    arrange_startup(monkeypatch, revision="obsolete_development_head")
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    message = str(caught.value)
    assert "obsolete_development_head" in message
    assert "0001_mvp_baseline" in message
    assert "python -m database.cli migrate" in message


def test_startup_rejects_missing_alembic_version_with_clear_guidance(monkeypatch):
    arrange_startup(monkeypatch, revision=None)
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    message = str(caught.value)
    assert "Database revision: missing" in message
    assert "Required revision: 0001_mvp_baseline" in message
    assert "python -m database.cli migrate" in message


def test_main_passes_runtime_storage_root_to_app_context():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "storage_root=settings.storage_root" in source
    assert "python -m database.cli migrate" in source
