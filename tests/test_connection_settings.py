from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

import app.connection_settings as connection_settings_module
from app.connection_settings import (
    DATABASE_ONLY,
    ConnectionProfile,
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


def profile(storage_root: Path) -> ConnectionProfile:
    return ConnectionProfile(
        name="Birkachan",
        host="db.internal",
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


def test_saved_profile_is_used_when_environment_is_not_configured(monkeypatch, tmp_path):
    clear_runtime_environment(monkeypatch)
    store, _credentials = make_store(tmp_path)
    store.save(profile(tmp_path))

    settings, source = resolve_runtime_settings(store)

    assert source == "saved"
    assert make_url(settings.database_url).host == "db.internal"
    assert settings.storage_root == tmp_path


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
    assert legacy.with_suffix(".ini.migrated").exists()
    assert "legacy-secret" not in store.path.read_text(encoding="utf-8")


def test_storage_validation_accepts_writable_folder(tmp_path):
    assert validate_storage_root(tmp_path) == tmp_path
    assert not list(tmp_path.glob(".slopeforge-write-test-*"))


def test_storage_validation_rejects_missing_folder(tmp_path):
    with pytest.raises(ConnectionSettingsError, match="does not exist"):
        validate_storage_root(tmp_path / "missing")


def test_first_run_setup_is_resolved_before_authentication():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "resolve_runtime_settings(connection_store)" in source
    assert "ConnectionSetupDialog" in source
    assert source.index("resolve_runtime_settings(connection_store)") < source.index(
        "AuthService(session_factory)"
    )
    assert "initialize_database_runtime(runtime_settings)" in source


def test_settings_dialog_exposes_connection_section():
    source = Path("ui/settings_dialog.py").read_text(encoding="utf-8")
    assert "ConnectionSettingsPage" in source
    assert 'self._add_page(tr("Connection"), ConnectionSettingsPage())' in source


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
