from __future__ import annotations

from pathlib import Path

import pytest

import database.startup as startup


CURRENT_HEAD = "1"
PRE_1_0_HEAD = "0003_drillhole_datasets"


def arrange_startup(monkeypatch, *, revision=CURRENT_HEAD, tables=()):
    from database.settings import Settings

    settings = Settings("postgresql+psycopg://u:p@localhost/db", Path("/tmp/storage"))
    engine = object()
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: engine)
    monkeypatch.setattr(startup, "check_connection", lambda value: None)
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: CURRENT_HEAD)
    monkeypatch.setattr(
        startup,
        "_database_alembic_heads",
        lambda value: () if revision is None else (revision,),
    )
    monkeypatch.setattr(startup, "_database_user_tables", lambda value: tuple(tables))
    monkeypatch.setattr(startup, "apply_migrations", lambda: None)
    monkeypatch.setattr(startup, "configure_mappers", lambda: None)
    monkeypatch.setattr(startup, "create_session_factory", lambda value: "sessions")
    return settings, engine


def test_empty_database_is_initialized_to_current_head(monkeypatch):
    settings, engine = arrange_startup(monkeypatch, revision=None, tables=())
    migrated = []
    monkeypatch.setattr(startup, "apply_migrations", lambda: migrated.append(True))
    monkeypatch.setattr(startup, "_database_alembic_heads", lambda value: (CURRENT_HEAD,))

    assert startup.initialize_database_runtime() == (settings, engine, "sessions")
    assert migrated == [True]


def test_current_database_revision_is_accepted(monkeypatch):
    settings, engine = arrange_startup(monkeypatch, revision=CURRENT_HEAD)
    assert startup.initialize_database_runtime() == (settings, engine, "sessions")


def test_older_numeric_database_requires_upgrade(monkeypatch):
    arrange_startup(monkeypatch, revision="0")
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    assert caught.value.reason == "database_upgrade_required"
    assert "older" in str(caught.value)


def test_newer_numeric_database_requires_newer_application(monkeypatch):
    arrange_startup(monkeypatch, revision="2")
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    assert caught.value.reason == "application_upgrade_required"
    assert "newer" in str(caught.value)


def test_real_script_directory_classifies_pre_1_0_revision_as_database_upgrade(monkeypatch):
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: CURRENT_HEAD)
    monkeypatch.setattr(startup, "_database_alembic_heads",
                        lambda _engine: (PRE_1_0_HEAD,))
    with pytest.raises(startup.StartupError) as caught:
        startup._verify_alembic_revision(object(), None)
    assert caught.value.reason == "database_upgrade_required"


def test_startup_initializes_a_completely_empty_database(monkeypatch):
    settings, engine = arrange_startup(monkeypatch, revision=None, tables=())
    assert startup.initialize_database_runtime() == (settings, engine, "sessions")


def test_startup_rejects_nonempty_unversioned_database(monkeypatch):
    arrange_startup(monkeypatch, revision=None, tables=("unmanaged_data",))
    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()
    assert caught.value.reason == "database_version_incompatible"
    assert "python -m" not in caught.value.presentation()


def test_runtime_controller_passes_runtime_storage_root_to_app_context():
    runtime_source = Path("app/runtime_controller.py").read_text(encoding="utf-8")
    main_source = Path("main.py").read_text(encoding="utf-8")

    assert "storage_root=settings.storage_root" in runtime_source
    assert "startup_error_handler=show_startup_error" in main_source
