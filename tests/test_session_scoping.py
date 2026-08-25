from __future__ import annotations

from datetime import datetime, timedelta, timezone

from infrastructure.services.session_service import (
    clear_local_session,
    legacy_session_file_path,
    load_local_session,
    save_local_session,
    session_file_path,
)


def test_remembered_session_files_are_isolated_per_connection_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    save_local_session("alice", "token-a", "PC", expires, scope_id="profile-a")
    save_local_session("bob", "token-b", "PC", expires, scope_id="profile-b")

    path_a = session_file_path("profile-a")
    path_b = session_file_path("profile-b")
    assert path_a != path_b
    assert path_a.parent == tmp_path / "SlopeForge" / "sessions"
    assert path_b.parent == path_a.parent
    assert "profile-a" not in path_a.name
    assert "profile-b" not in path_b.name
    assert load_local_session("profile-a")["token"] == "token-a"
    assert load_local_session("profile-b")["token"] == "token-b"

    clear_local_session("profile-a")
    assert load_local_session("profile-a") is None
    assert load_local_session("profile-b")["username"] == "bob"


def test_legacy_session_file_is_separate_from_scoped_sessions(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert legacy_session_file_path() == tmp_path / "SlopeForge" / "session.json"
    assert session_file_path("profile-a").parent == tmp_path / "SlopeForge" / "sessions"
    assert session_file_path("profile-a") != legacy_session_file_path()


def test_runtime_controller_scopes_remembered_login_to_selected_profile():
    source = open("app/runtime_controller.py", encoding="utf-8").read()
    assert "scope_id=scope_id" in source
    assert "target.profile.profile_id" in source
    assert "migrate_legacy=True" in source
