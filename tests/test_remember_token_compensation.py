from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import infrastructure.services.session_service as session_service
from infrastructure.services.session_service import RememberTokenService, save_local_session


class FakeSession:
    def __init__(self, shared):
        self.shared = shared
        self.commit_calls = 0
        self.rollback_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, value):
        self.shared["remember"] = value

    def scalar(self, _statement):
        return self.shared.get("remember")

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


class FakeSessionFactory:
    def __init__(self):
        self.shared = {}
        self.sessions = []

    def __call__(self):
        session = FakeSession(self.shared)
        self.sessions.append(session)
        return session


def test_local_session_write_failure_revokes_committed_server_token(monkeypatch):
    factory = FakeSessionFactory()
    service = RememberTokenService(factory, scope_id="profile-a")
    monkeypatch.setattr(
        session_service,
        "save_local_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        service.create_for_user(7, "engineer", "workstation")

    remember = factory.shared["remember"]
    assert remember.revoked_at is not None
    assert len(factory.sessions) == 2
    assert factory.sessions[0].commit_calls == 1
    assert factory.sessions[1].commit_calls == 1


def test_failed_atomic_local_session_replace_does_not_leave_plaintext_temp(monkeypatch, tmp_path):
    monkeypatch.setattr(session_service, "_config_directory", lambda: tmp_path)
    monkeypatch.setattr(
        session_service.os,
        "replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("replace failed")),
    )
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    with pytest.raises(OSError, match="replace failed"):
        save_local_session(
            "engineer",
            "raw-secret-token",
            "workstation",
            expires,
            scope_id="profile-a",
        )

    target = session_service.session_file_path("profile-a")
    assert not target.exists()
    assert not target.with_suffix(target.suffix + ".tmp").exists()
    assert all(
        "raw-secret-token" not in path.read_text(encoding="utf-8", errors="ignore")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
