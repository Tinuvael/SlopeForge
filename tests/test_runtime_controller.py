from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.connection_settings import DATABASE_ONLY, ConnectionProfile
from app.runtime_controller import (
    ActiveDesktopRuntime,
    DesktopRuntimeController,
    RuntimeTarget,
)


class FakeStore:
    def __init__(self, profiles=()):
        self.profiles = {item.profile_id: item for item in profiles}
        self.used = []
        self.auto = None

    def runtime_profile(self, profile_id):
        return self.profiles[profile_id]

    def mark_used(self, profile_id):
        self.used.append(profile_id)

    def set_auto_connect_profile(self, profile_id):
        self.auto = profile_id


class FakeWindow:
    def __init__(self, events, name):
        self.events = events
        self.name = name
        self.closed = False
        self.deleted = False
        self.guard_result = True

    def showMaximized(self):
        self.events.append(f"show:{self.name}")

    def close(self):
        self.closed = True
        self.events.append(f"close:{self.name}")

    def deleteLater(self):
        self.deleted = True
        self.events.append(f"delete:{self.name}")

    def _guard_leave(self):
        self.events.append(f"guard:{self.name}")
        return self.guard_result


class FakeEngine:
    def __init__(self, events, name):
        self.events = events
        self.name = name
        self.disposed = False

    def dispose(self):
        self.disposed = True
        self.events.append(f"dispose:{self.name}")


def profile(profile_id: str, name: str) -> ConnectionProfile:
    return ConnectionProfile(
        profile_id=profile_id,
        name=name,
        host=f"{profile_id}.example",
        database="slopeforge",
        username="viewer",
        mode=DATABASE_ONLY,
    )


def target(item: ConnectionProfile) -> RuntimeTarget:
    return RuntimeTarget(item, item.to_settings(), "saved")


def active(item: ConnectionProfile, events, name: str) -> ActiveDesktopRuntime:
    return ActiveDesktopRuntime(
        target=target(item),
        settings=item.to_settings(),
        engine=FakeEngine(events, name),
        session_factory=object(),
        window=FakeWindow(events, name),
    )


def controller(store: FakeStore) -> DesktopRuntimeController:
    return DesktopRuntimeController(
        SimpleNamespace(),
        store,
        startup_error_handler=lambda _error: "close",
        splash_factory=lambda: None,
    )


def test_commit_shows_new_window_before_disposing_previous_runtime():
    events = []
    old_profile = profile("old", "Old server")
    new_profile = profile("new", "New server")
    store = FakeStore((old_profile, new_profile))
    control = controller(store)
    old = active(old_profile, events, "old")
    new = active(new_profile, events, "new")
    control.current = old

    control._commit_runtime(new, previous=old)

    assert events == ["show:new", "close:old", "delete:old", "dispose:old"]
    assert control.current is new
    assert old.window.closed is True
    assert old.engine.disposed is True
    assert store.used == ["new"]


def test_failed_replacement_keeps_previous_runtime_alive(monkeypatch):
    events = []
    old_profile = profile("old", "Old server")
    new_profile = profile("new", "New server")
    store = FakeStore((old_profile, new_profile))
    control = controller(store)
    old = active(old_profile, events, "old")
    control.current = old
    monkeypatch.setattr(control, "_confirm_switch", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(control, "_build_runtime", lambda *_args, **_kwargs: None)

    assert control.request_switch("new") is False

    assert control.current is old
    assert old.window.closed is False
    assert old.engine.disposed is False
    assert events == ["guard:old"]


def test_cancelled_unsaved_work_guard_never_builds_replacement(monkeypatch):
    events = []
    old_profile = profile("old", "Old server")
    new_profile = profile("new", "New server")
    store = FakeStore((old_profile, new_profile))
    control = controller(store)
    old = active(old_profile, events, "old")
    old.window.guard_result = False
    control.current = old
    monkeypatch.setattr(control, "_confirm_switch", lambda *_args, **_kwargs: True)
    built = []
    monkeypatch.setattr(control, "_build_runtime", lambda *_args, **_kwargs: built.append(True))

    assert control.request_switch("new") is False

    assert built == []
    assert control.current is old
    assert old.window.closed is False
    assert old.engine.disposed is False
    assert events == ["guard:old"]


def test_same_profile_does_not_rebuild_runtime(monkeypatch):
    events = []
    item = profile("same", "Same server")
    store = FakeStore((item,))
    control = controller(store)
    old = active(item, events, "same")
    control.current = old
    built = []
    monkeypatch.setattr(control, "_build_runtime", lambda *_args, **_kwargs: built.append(True))

    assert control.request_switch("same") is True

    assert built == []
    assert control.current is old
    assert old.engine.disposed is False
