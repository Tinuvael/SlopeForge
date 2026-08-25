from __future__ import annotations

from datetime import datetime, timedelta, timezone

import infrastructure.services.session_service as session_service
from app.context import CurrentUser
from infrastructure.services.session_service import (
    clear_local_session,
    load_local_session,
    save_local_session,
    session_file_path,
    token_hash,
)
from infrastructure.services.user_admin_service import UserAdminPermissionError, UserAdminService


def test_remember_token_hash_does_not_store_plain_token() -> None:
    raw = "plain-token"
    hashed = token_hash(raw)
    assert hashed != raw
    assert len(hashed) == 64
    assert token_hash(raw) == hashed


def test_remembered_session_files_are_scoped_per_server_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(session_service, "_config_directory", lambda: tmp_path)
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    save_local_session("alice", "token-a", "pc", expires, scope_id="profile-a")
    save_local_session("bob", "token-b", "pc", expires, scope_id="profile-b")

    assert session_file_path("profile-a") != session_file_path("profile-b")
    assert load_local_session("profile-a")["token"] == "token-a"
    assert load_local_session("profile-b")["token"] == "token-b"
    assert load_local_session(None) is None

    clear_local_session("profile-a")
    assert load_local_session("profile-a") is None
    assert load_local_session("profile-b")["token"] == "token-b"


def test_legacy_session_path_is_separate_from_profile_scopes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(session_service, "_config_directory", lambda: tmp_path)
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    save_local_session("legacy", "legacy-token", "pc", expires, scope_id=None)

    assert load_local_session(None)["token"] == "legacy-token"
    assert load_local_session("profile-a") is None
    assert session_file_path(None).name == "session.json"
    assert session_file_path("profile-a").parent.name == "sessions"


def test_user_admin_requires_admin_role() -> None:
    service = UserAdminService(lambda: None)
    viewer = CurrentUser(1, "viewer", None, "viewer")
    try:
        service.list_users(viewer)
    except UserAdminPermissionError:
        pass
    else:
        raise AssertionError("viewer must not manage users")
