from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import database.startup as startup
from database.settings import Settings


CURRENT_HEAD = "0002_project_surface_datasets"
BASELINE = "0001_mvp_baseline"


class FakeInspector:
    def __init__(self, tables=()): self.tables = tables
    def get_table_names(self): return list(self.tables)


def test_expected_alembic_head_resolves_real_repository_graph():
    """Exercise the production path/config rather than a mocked head helper."""
    repository_heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    assert repository_heads == [CURRENT_HEAD]
    assert startup._expected_alembic_head() == repository_heads[0]


class FakeScript:
    def get_revision(self, revision):
        return object() if revision in {BASELINE, CURRENT_HEAD} else None


def arrange_startup(monkeypatch, *, revision=CURRENT_HEAD, tables=None):
    settings = Settings("postgresql+psycopg://u:secret@db.example:5432/slopeforge", Path("/tmp/storage"))
    engine = object()
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: engine)
    monkeypatch.setattr(startup, "create_session_factory", lambda value: "sessions")
    monkeypatch.setattr(startup, "check_connection", lambda value: None)
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: CURRENT_HEAD)
    monkeypatch.setattr(startup, "_alembic_script", lambda: FakeScript())
    state = {
        "revision": revision,
        "tables": startup.Base.metadata.tables if tables is None else tables,
    }
    monkeypatch.setattr(
        startup, "_database_alembic_heads",
        lambda value: (() if state["revision"] is None else (state["revision"],)),
    )
    def upgrade(_settings):
        state["revision"] = CURRENT_HEAD
        state["tables"] = startup.Base.metadata.tables
    monkeypatch.setattr(startup, "upgrade_to_head", upgrade)
    monkeypatch.setattr(startup, "configure_mappers", lambda: None)
    monkeypatch.setattr(startup, "inspect", lambda value: FakeInspector(state["tables"]))
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


def test_startup_known_older_revision_requires_migration(monkeypatch):
    arrange_startup(monkeypatch, revision=BASELINE)
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    assert caught.value.reason == "database_migration_required"
    rendered = caught.value.presentation()
    assert BASELINE in rendered
    assert CURRENT_HEAD in rendered


def test_startup_removed_revision_requires_reset_not_migrate(monkeypatch):
    arrange_startup(monkeypatch, revision="20260809_0008")
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    rendered = caught.value.presentation()
    assert caught.value.reason == "database_revision_obsolete"
    assert "20260809_0008" in rendered
    assert CURRENT_HEAD in rendered
    assert "reset-dev-db" in rendered
    assert "database.cli migrate" not in rendered


def test_real_script_directory_classifies_removed_revision(monkeypatch):
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: CURRENT_HEAD)
    monkeypatch.setattr(startup, "_database_alembic_heads",
                        lambda _engine: ("20260809_0008",))
    with pytest.raises(startup.StartupError) as caught:
        startup._verify_alembic_revision(object(), None)
    assert caught.value.reason == "database_revision_obsolete"


def test_startup_initializes_a_completely_empty_database(monkeypatch):
    settings, engine = arrange_startup(monkeypatch, revision=None, tables=())
    assert startup.initialize_database_runtime() == (settings, engine, "sessions")


def test_startup_rejects_nonempty_unversioned_database(monkeypatch):
    arrange_startup(monkeypatch, revision=None, tables=("unmanaged_data",))
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    assert caught.value.reason == "database_migration_required"
    assert "not empty" in str(caught.value)
    assert "database.cli migrate" not in caught.value.presentation()


def test_main_passes_runtime_storage_root_to_app_context():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "storage_root=settings.storage_root" in source
    assert "show_startup_error(exc)" in source
