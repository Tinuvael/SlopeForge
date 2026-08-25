from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

import app.connection_settings as connection_settings_module
from app.connection_settings import (
    DATABASE_ONLY,
    ConnectionProfile,
    ConnectionSelectionRequired,
    ConnectionSettingsError,
    ConnectionSettingsStore,
    MissingConnectionConfiguration,
    resolve_runtime_settings,
    validate_storage_root,
)
from app.credential_store import MemoryCredentialStore


@pytest.fixture(autouse=True)
def isolate_local_env(monkeypatch):
    monkeypatch.setattr(connection_settings_module, "load_local_env", lambda: None)


def clear_runtime_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("STORAGE_ROOT", raising=False)


def make_store(tmp_path):
    credentials = MemoryCredentialStore()
    return ConnectionSettingsStore(
        tmp_path / "connections.json",
        credential_store=credentials,
        legacy_path=tmp_path / "connection.ini",
    ), credentials


def profile(storage_root: Path, *, name="Birkachan", host="db.internal") -> ConnectionProfile:
    return ConnectionProfile(
        name=name,
        host=host,
        port=5433,
        database="slopeforge",
        username="engineer",
        password="p@ss:/word",
        storage_root=storage_root,
    )


def test_saved_connection_profile_round_trips_without_plaintext_password(tmp_path):
    store, credentials = make_store(tmp_path)
    saved = store.save(profile(tmp_path))

    loaded = store.runtime_profile(saved.profile_id)

    assert loaded.host == "db.internal"
    assert loaded.password == "p@ss:/word"
    text = store.path.read_text(encoding="utf-8")
    assert "db.internal" in text
    assert "p@ss:/word" not in text
    assert credentials.read(saved.profile_id) == "p@ss:/word"


def test_profile_builds_psycopg_url_without_losing_special_password(tmp_path):
    settings = profile(tmp_path).to_settings()
    url = make_url(settings.database_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db.internal"
    assert url.port == 5433
    assert url.database == "slopeforge"
    assert url.username == "engineer"
    assert url.password == "p@ss:/word"
    assert settings.storage_root == tmp_path


def test_database_only_profile_does_not_require_storage():
    item = ConnectionProfile(
        name="Management viewer",
        host="db.internal",
        database="slopeforge",
        username="viewer",
        mode=DATABASE_ONLY,
    )
    item.validate_required()
    assert item.to_settings().storage_root is None


def test_saved_profile_is_used_by_noninteractive_resolver_when_only_one_exists(monkeypatch, tmp_path):
    clear_runtime_environment(monkeypatch)
    store, _credentials = make_store(tmp_path)
    store.save(profile(tmp_path))

    settings, source = resolve_runtime_settings(store)

    assert source == "saved"
    assert make_url(settings.database_url).host == "db.internal"
    assert settings.storage_root == tmp_path


def test_multiple_saved_profiles_require_explicit_selection_for_noninteractive_resolver(monkeypatch, tmp_path):
    clear_runtime_environment(monkeypatch)
    store, _credentials = make_store(tmp_path)
    first = store.upsert(profile(tmp_path), force_new=True)
    second = store.upsert(
        profile(tmp_path, name="Nevenrekan", host="db-2.internal"),
        force_new=True,
    )

    with pytest.raises(ConnectionSelectionRequired):
        resolve_runtime_settings(store)

    settings, source = resolve_runtime_settings(store, profile_id=second.profile_id)
    assert source == "saved"
    assert make_url(settings.database_url).host == "db-2.internal"
    assert first.profile_id != second.profile_id


def test_auto_connect_profile_is_independent_of_last_used_profile(tmp_path):
    store, _credentials = make_store(tmp_path)
    first = store.upsert(profile(tmp_path), force_new=True)
    second = store.upsert(
        profile(tmp_path, name="Nevenrekan", host="db-2.internal"),
        force_new=True,
    )
    store.set_auto_connect_profile(first.profile_id)
    store.mark_used(second.profile_id)

    assert store.auto_connect_profile_id() == first.profile_id
    assert store.last_profile_id() == second.profile_id


def test_complete_environment_configuration_overrides_saved_profile(monkeypatch, tmp_path):
    store, _credentials = make_store(tmp_path)
    store.save(profile(tmp_path))
    environment_url = (
        "postgresql+psycopg://env_user:env_password@env-host:5432/env_db"
        "?connect_timeout=9"
    )
    monkeypatch.setenv("DATABASE_URL", environment_url)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "env-storage"))

    settings, source = resolve_runtime_settings(store)

    assert source == "environment"
    assert settings.database_url == environment_url
    assert settings.storage_root == tmp_path / "env-storage"


def test_database_url_without_storage_root_is_database_only_environment(monkeypatch, tmp_path):
    store, _credentials = make_store(tmp_path)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://viewer:secret@remote-db:5432/slopeforge",
    )
    monkeypatch.delenv("STORAGE_ROOT", raising=False)

    settings, source = resolve_runtime_settings(store)

    assert source == "environment"
    assert settings.database_only is True
    assert settings.storage_root is None


def test_missing_configuration_requests_first_run_setup(monkeypatch, tmp_path):
    clear_runtime_environment(monkeypatch)
    store, _credentials = make_store(tmp_path)

    with pytest.raises(MissingConnectionConfiguration):
        resolve_runtime_settings(store)


def test_legacy_connection_ini_migrates_secret_out_of_plaintext(tmp_path):
    legacy = tmp_path / "connection.ini"
    legacy.write_text(
        "[connection]\n"
        "host=localhost\n"
        "port=5432\n"
        "database=slopeforge\n"
        "username=postgres\n"
        "password=legacy-secret\n"
        f"storage_root={tmp_path.as_posix()}\n",
        encoding="utf-8",
    )
    store, credentials = make_store(tmp_path)

    items = store.list_profiles()

    assert len(items) == 1
    assert credentials.read(items[0].profile_id) == "legacy-secret"
    assert not legacy.exists()
    assert not legacy.with_suffix(".ini.migrated").exists()
    assert "legacy-secret" not in store.path.read_text(encoding="utf-8")
    assert all(
        "legacy-secret" not in path.read_text(encoding="utf-8", errors="ignore")
        for path in tmp_path.iterdir()
        if path.is_file()
    )


def test_storage_validation_accepts_writable_folder(tmp_path):
    assert validate_storage_root(tmp_path) == tmp_path
    assert not list(tmp_path.glob(".slopeforge-write-test-*"))


def test_storage_validation_rejects_missing_folder(tmp_path):
    with pytest.raises(ConnectionSettingsError, match="does not exist"):
        validate_storage_root(tmp_path / "missing")


def test_desktop_runtime_selects_server_before_authentication():
    source = Path("app/runtime_controller.py").read_text(encoding="utf-8")
    assert "ServerSelectionDialog" in source
    assert "AuthService(session_factory)" in source
    assert source.index("def initial_target") < source.index("def _authenticate")
    assert "Selection is deliberately shown even when only one profile exists" in source


def test_settings_dialog_exposes_connections_section_with_runtime_context():
    source = Path("ui/settings_dialog.py").read_text(encoding="utf-8")
    assert "ConnectionSettingsPage" in source
    assert 'self._add_page(tr("Connections"), ConnectionSettingsPage(context=context))' in source


def test_database_startup_accepts_explicit_settings():
    source = Path("database/startup.py").read_text(encoding="utf-8")
    assert "def initialize_database_runtime(settings: Settings | None = None):" in source
    assert "runtime_settings = runtime_settings or Settings.from_env()" in source


def test_alembic_uses_same_saved_connection_resolver_as_desktop():
    source = Path("alembic/env.py").read_text(encoding="utf-8")
    assert "from app.connection_settings import resolve_runtime_settings" in source
    assert "settings, _source = resolve_runtime_settings()" in source
    assert "Settings.from_env()" not in source


def test_database_cli_uses_saved_connection_resolver_without_requiring_env():
    source = Path("database/cli.py").read_text(encoding="utf-8")
    assert "from app.connection_settings import ConnectionSettingsError, resolve_runtime_settings" in source
    assert "settings, _source = resolve_runtime_settings()" in source
    assert "Settings.from_env()" not in source