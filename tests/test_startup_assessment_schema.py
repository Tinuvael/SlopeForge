from pathlib import Path

import pytest

import database.startup as startup
from database.settings import Settings


class FakeInspector:
    def get_table_names(self):
        return []


def test_startup_requires_assessment_tables_and_does_not_run_migrations(monkeypatch):
    settings = Settings("postgresql+psycopg://u:p@localhost/db", Path("/tmp/storage"))
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: object())
    monkeypatch.setattr(startup, "check_connection", lambda engine: None)
    monkeypatch.setattr(startup, "inspect", lambda engine: FakeInspector())

    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()

    message = str(caught.value)
    assert "assessment_" in message or "blast_event_" in message
    assert "assessment_workspaces" not in startup.Base.metadata.tables
    assert "blast_events" in startup.Base.metadata.tables
    assert "assessment_entity_attachments" in startup.Base.metadata.tables


def test_main_passes_runtime_storage_root_to_app_context():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "storage_root=settings.storage_root" in source
    assert "python -m database.cli migrate" in source
