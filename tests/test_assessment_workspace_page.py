from pathlib import Path
from types import SimpleNamespace

import pytest
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QWidget

import ui.pages.assessment_workspace_page as page_module


class FakeRepository:
    loaded = []
    replacements = []
    state = object()
    fail_save = False

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def load_for_site(self, site_id):
        self.loaded.append(site_id)
        return SimpleNamespace(workspace_id=12, state=self.state)

    def replace_for_site(self, site_id, state):
        self.replacements.append((site_id, state))
        if self.fail_save:
            raise RuntimeError("database unavailable")
        return SimpleNamespace(workspace_id=34, state=object())


class FakeWorkspace(QWidget):
    state_changed = Signal()
    state_saved = Signal()

    def __init__(self, state, storage_path, save_callback, parent=None):
        super().__init__(parent)
        self.state, self.storage_path = state, storage_path
        self.save_callback, self.calls = save_callback, []

    def open_blast_event(self, value): self.calls.append(("event", value)); return True
    def open_assessment_area(self, value): self.calls.append(("area", value)); return True
    def open_dataset(self, value): self.calls.append(("dataset", value)); return True
    def refresh_workspace(self): self.calls.append(("refresh",))
    def has_active_workflow(self): return True
    def cancel_active_workflow(self): self.calls.append(("cancel",)); return True
    def save_now(self): self.calls.append(("save",))


@pytest.fixture
def page(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    FakeRepository.loaded = []
    FakeRepository.replacements = []
    FakeRepository.fail_save = False
    monkeypatch.setattr(page_module, "AssessmentStateRepository", FakeRepository)
    monkeypatch.setattr(page_module, "AssessmentWorkspaceWidget", FakeWorkspace)
    context = SimpleNamespace(session_factory=object(), storage_root=tmp_path)
    return page_module.AssessmentWorkspacePage(context, 7, "Северный")


def test_loads_site_state_workspace_id_anchor_label_and_signals(page, tmp_path):
    assert FakeRepository.loaded == [7]
    assert page.state is FakeRepository.state
    assert page.workspace.state is page.state
    assert page.workspace_id == 12
    assert page.storage_path == tmp_path / "slopeforge_state.json"
    assert not page.storage_path.exists()
    assert "Северный" in page.domain_label.text()
    assert page.state_changed is page.workspace.state_changed
    assert page.state_saved is page.workspace.state_saved


def test_save_replaces_same_in_memory_state_and_updates_workspace_id(page):
    page.workspace.save_callback()
    assert FakeRepository.replacements == [(7, page.state)]
    assert page.workspace_id == 34
    assert page.state is FakeRepository.state


def test_repository_save_errors_propagate(page):
    FakeRepository.fail_save = True
    with pytest.raises(RuntimeError, match="database unavailable"):
        page.workspace.save_callback()


def test_public_delegation(page):
    assert page.open_blast_event("e")
    assert page.open_assessment_area("a")
    assert page.open_dataset("d")
    page.refresh_workspace()
    assert page.has_active_workflow()
    assert page.cancel_active_workflow()
    page.save_now()
    assert page.workspace.calls == [("event", "e"), ("area", "a"), ("dataset", "d"),
                                    ("refresh",), ("cancel",), ("save",)]


def test_site_id_is_domain_label_fallback(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(page_module, "AssessmentStateRepository", FakeRepository)
    monkeypatch.setattr(page_module, "AssessmentWorkspaceWidget", FakeWorkspace)
    context = SimpleNamespace(session_factory=object(), storage_root=tmp_path)
    page = page_module.AssessmentWorkspacePage(context, 99)
    assert "99" in page.domain_label.text()


def test_active_page_has_no_json_storage_dependency():
    source = Path(page_module.__file__).read_text(encoding="utf-8")
    assert "blast_event_storage" not in source
    assert "load_blast_event_state" not in source
    assert "save_blast_event_state" not in source
