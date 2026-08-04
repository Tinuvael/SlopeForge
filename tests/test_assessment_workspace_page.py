from pathlib import Path

import pytest
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QWidget

import ui.pages.assessment_workspace_page as page_module


class FakeWorkspace(QWidget):
    state_changed = Signal()
    state_saved = Signal()

    def __init__(self, state, storage_path, save_callback, parent=None):
        super().__init__(parent)
        self.state = state
        self.storage_path = storage_path
        self.save_callback = save_callback
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("open_"):
            return lambda value: self.calls.append((name, value)) or True
        if name in {"refresh_workspace", "save_now"}:
            return lambda: self.calls.append((name,))
        if name == "has_active_workflow":
            return lambda: True
        if name == "cancel_active_workflow":
            return lambda: self.calls.append((name,)) or True
        raise AttributeError(name)


def test_page_owns_one_loaded_state_path_signals_and_persistence(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    target = tmp_path / "nested" / "events.json"
    state = object()
    loaded = []
    saved = []
    monkeypatch.setattr(page_module, "default_blast_event_storage_path", lambda: target)
    monkeypatch.setattr(page_module, "load_blast_event_state", lambda path: loaded.append(path) or state)
    monkeypatch.setattr(page_module, "save_blast_event_state", lambda value, path: saved.append((value, path)))
    monkeypatch.setattr(page_module, "AssessmentWorkspaceWidget", FakeWorkspace)

    page = page_module.AssessmentWorkspacePage()
    assert page.storage_path == target
    assert loaded == [target]
    assert page.state is state and page.workspace.state is state
    assert page.workspace.storage_path == target
    assert page.workspace.storage_path.parent == target.parent
    assert page.state_changed is page.workspace.state_changed
    assert page.state_saved is page.workspace.state_saved
    page.workspace.save_callback()
    assert saved == [(state, target)]


def test_explicit_path_and_public_delegation(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    target = tmp_path / "events.json"
    monkeypatch.setattr(page_module, "load_blast_event_state", lambda path: object())
    monkeypatch.setattr(page_module, "AssessmentWorkspaceWidget", FakeWorkspace)
    page = page_module.AssessmentWorkspacePage(str(target))

    assert page.open_blast_event("event") is True
    assert page.open_assessment_area("area") is True
    assert page.open_dataset("dataset") is True
    page.refresh_workspace()
    assert page.has_active_workflow() is True
    assert page.cancel_active_workflow() is True
    page.save_now()
    assert page.workspace.calls == [
        ("open_blast_event", "event"), ("open_assessment_area", "area"),
        ("open_dataset", "dataset"), ("refresh_workspace",),
        ("cancel_active_workflow",), ("save_now",),
    ]
