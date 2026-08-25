from __future__ import annotations

from dataclasses import replace

import pytest

from app.connection_settings import (
    ConnectionProfile,
    ConnectionSettingsError,
    ConnectionSettingsStore,
)
from app.credential_store import MemoryCredentialStore


class FailingWriteStore(ConnectionSettingsStore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_writes = False

    def _write_document(self, data: dict) -> None:
        if self.fail_writes:
            raise ConnectionSettingsError("simulated metadata write failure")
        super()._write_document(data)


def _profile(tmp_path, *, profile_id="", password="old-secret"):
    return ConnectionProfile(
        profile_id=profile_id,
        name="Production",
        host="db.example",
        database="slopeforge",
        username="engineer",
        password=password,
        storage_root=tmp_path,
    )


def _store(tmp_path):
    credentials = MemoryCredentialStore()
    store = FailingWriteStore(
        tmp_path / "connections.json",
        credential_store=credentials,
        legacy_path=tmp_path / "connection.ini",
    )
    return store, credentials


def test_failed_profile_update_restores_previous_credential_and_metadata(tmp_path):
    store, credentials = _store(tmp_path)
    saved = store.upsert(_profile(tmp_path), force_new=True)
    before = store.path.read_text(encoding="utf-8")
    assert credentials.read(saved.profile_id) == "old-secret"

    store.fail_writes = True
    changed = replace(saved, host="new-db.example", password="new-secret")
    with pytest.raises(ConnectionSettingsError, match="simulated metadata write failure"):
        store.upsert(changed, password="new-secret")

    assert store.path.read_text(encoding="utf-8") == before
    assert credentials.read(saved.profile_id) == "old-secret"


def test_failed_new_profile_write_removes_new_credential(tmp_path):
    store, credentials = _store(tmp_path)
    store.fail_writes = True

    with pytest.raises(ConnectionSettingsError, match="simulated metadata write failure"):
        store.upsert(_profile(tmp_path), password="new-secret", force_new=True)

    assert credentials.values == {}
    assert not store.path.exists()


def test_failed_profile_removal_restores_credential_and_keeps_metadata(tmp_path):
    store, credentials = _store(tmp_path)
    saved = store.upsert(_profile(tmp_path), force_new=True)
    before = store.path.read_text(encoding="utf-8")

    store.fail_writes = True
    with pytest.raises(ConnectionSettingsError, match="simulated metadata write failure"):
        store.remove(saved.profile_id)

    assert store.path.read_text(encoding="utf-8") == before
    assert credentials.read(saved.profile_id) == "old-secret"


def test_legacy_migration_does_not_enable_startup_auto_connect(tmp_path):
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
    store, credentials = _store(tmp_path)

    profiles = store.list_profiles()

    assert len(profiles) == 1
    assert store.last_profile_id() == profiles[0].profile_id
    assert store.auto_connect_profile_id() is None
    assert credentials.read(profiles[0].profile_id) == "legacy-secret"
    assert not legacy.exists()
