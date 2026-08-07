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
    state = None
    fail_save = False

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def load_for_domain(self, domain_id):
        self.loaded.append(domain_id)
        if self.state is None:
            self.state = SimpleNamespace(datasets=[], blast_events=[], assessment_areas=[], technical_cards=[], evaluations=[], attachments=[])
        return SimpleNamespace(domain_id=domain_id, site_id=70, workspace_id=12, state=self.state)

    def replace_for_domain(self, domain_id, state):
        self.replacements.append((domain_id, state))
        if self.fail_save:
            raise RuntimeError("database unavailable")
        return SimpleNamespace(workspace_id=34, state=object())


class FakeWorkspace(QWidget):
    state_changed = Signal()
    state_saved = Signal()

    def __init__(self, state, storage_path, save_callback, parent=None, read_only=False, persist_dataset_callback=None, set_active_dataset_callback=None):
        super().__init__(parent)
        self.state, self.storage_path = state, storage_path
        self.save_callback, self.calls = save_callback, []
        self.read_only = read_only
        self.persist_dataset_callback = persist_dataset_callback
        self.set_active_dataset_callback = set_active_dataset_callback
        self.fail_refresh = False

    def open_blast_event(self, value): self.calls.append(("event", value)); return True
    def open_assessment_area(self, value): self.calls.append(("area", value)); return True
    def open_dataset(self, value): self.calls.append(("dataset", value)); return True
    def refresh_workspace(self):
        self.calls.append(("refresh",))
        if self.fail_refresh:
            raise RuntimeError("refresh failed")
    def has_active_workflow(self): return True
    def cancel_active_workflow(self): self.calls.append(("cancel",)); return True
    def save_now(self):
        self.calls.append(("save",))
        if not self.read_only:
            self.save_callback()


class FakeProjectLinesRepository:
    added = []
    activated = []

    def __init__(self, session_factory): pass
    def import_dataset(self, site_id, dataset, *, make_active=True):
        self.added.append((site_id, dataset.id, make_active))
    def set_active(self, site_id, dataset_id): self.activated.append((site_id, dataset_id))


@pytest.fixture
def page(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    FakeRepository.loaded = []
    FakeRepository.replacements = []
    FakeRepository.fail_save = False
    FakeRepository.state = SimpleNamespace(datasets=[], blast_events=[], assessment_areas=[], technical_cards=[], evaluations=[], attachments=[])
    monkeypatch.setattr(page_module, "AssessmentStateRepository", FakeRepository)
    monkeypatch.setattr(page_module, "ProjectLinesRepository", FakeProjectLinesRepository)
    monkeypatch.setattr(page_module, "AssessmentWorkspaceWidget", FakeWorkspace)
    context = SimpleNamespace(session_factory=object(), storage_root=tmp_path,
                              current_user=SimpleNamespace(can_edit=True))
    return page_module.AssessmentWorkspacePage(context, 7, "Северный")


def test_dataset_callbacks_use_explicit_site_repository(page):
    FakeProjectLinesRepository.added = []
    FakeProjectLinesRepository.activated = []
    dataset = SimpleNamespace(id="D-001", is_active=True)
    page.workspace.persist_dataset_callback(dataset)
    assert FakeProjectLinesRepository.added == [(70, "D-001", True)]
    assert FakeProjectLinesRepository.activated == []
    page.workspace.set_active_dataset_callback("D-002")
    assert FakeProjectLinesRepository.activated[-1] == (70, "D-002")


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


def test_viewer_save_is_rejected_without_replacing(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    FakeRepository.loaded = []
    FakeRepository.replacements = []
    FakeRepository.state = SimpleNamespace(datasets=[], blast_events=[], assessment_areas=[], technical_cards=[], evaluations=[], attachments=[])
    monkeypatch.setattr(page_module, "AssessmentStateRepository", FakeRepository)
    monkeypatch.setattr(page_module, "AssessmentWorkspaceWidget", FakeWorkspace)
    context = SimpleNamespace(session_factory=object(), storage_root=tmp_path,
                              current_user=SimpleNamespace(can_edit=False))

    page = page_module.AssessmentWorkspacePage(context, 7, "Viewer")

    assert page.workspace.read_only is True
    with pytest.raises(PermissionError):
        page.workspace.save_callback()
    assert FakeRepository.replacements == []
    assert page.workspace_id == 12

    page.save_now()
    assert FakeRepository.replacements == []
    assert page.workspace_id == 12


def test_reload_preserves_state_identity_and_replaces_collections(page):
    old_state = page.state
    selected_event = SimpleNamespace(id="old-event")
    selected_area = SimpleNamespace(id="old-area")
    page.workspace.selected_event = selected_event
    page.workspace.selected_area = selected_area
    new_state = SimpleNamespace(
        datasets=["dataset"], blast_events=[SimpleNamespace(id="new-event")],
        assessment_areas=[SimpleNamespace(id="new-area")], technical_cards=["card"],
        evaluations=["evaluation"], attachments=["attachment"],
    )
    page.repository.load_for_domain = lambda domain_id: SimpleNamespace(site_id=70, workspace_id=99, state=new_state)

    page.reload_from_repository()

    assert page.state is old_state
    assert page.workspace.state is old_state
    assert page.workspace_id == 99
    assert old_state.datasets == ["dataset"]
    assert old_state.blast_events == new_state.blast_events
    assert old_state.assessment_areas == new_state.assessment_areas
    assert old_state.technical_cards == ["card"]
    assert old_state.evaluations == ["evaluation"]
    assert old_state.attachments == ["attachment"]
    assert ("refresh",) in page.workspace.calls


def test_reload_refresh_failure_rolls_back_previous_state(page):
    old_state = page.state
    old_state.datasets[:] = ["old-dataset"]
    old_state.blast_events[:] = ["old-event"]
    old_state.assessment_areas[:] = ["old-area"]
    old_state.technical_cards[:] = ["old-card"]
    old_state.evaluations[:] = ["old-evaluation"]
    old_state.attachments[:] = ["old-attachment"]
    old_workspace_id = page.workspace_id
    new_state = SimpleNamespace(
        datasets=["new-dataset"], blast_events=["new-event"], assessment_areas=["new-area"],
        technical_cards=["new-card"], evaluations=["new-evaluation"], attachments=["new-attachment"],
    )
    page.repository.load_for_domain = lambda domain_id: SimpleNamespace(site_id=70, workspace_id=77, state=new_state)
    page.workspace.fail_refresh = True

    with pytest.raises(RuntimeError, match="refresh failed"):
        page.reload_from_repository()

    assert page.state is old_state
    assert page.workspace_id == old_workspace_id
    assert old_state.datasets == ["old-dataset"]
    assert old_state.blast_events == ["old-event"]
    assert old_state.assessment_areas == ["old-area"]
    assert old_state.technical_cards == ["old-card"]
    assert old_state.evaluations == ["old-evaluation"]
    assert old_state.attachments == ["old-attachment"]


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
    context = SimpleNamespace(session_factory=object(), storage_root=tmp_path,
                              current_user=SimpleNamespace(can_edit=True))
    page = page_module.AssessmentWorkspacePage(context, 99)
    assert "99" in page.domain_label.text()


def test_active_page_has_no_json_storage_dependency():
    source = Path(page_module.__file__).read_text(encoding="utf-8")
    assert "blast_event_storage" not in source
    assert "load_blast_event_state" not in source
    assert "save_blast_event_state" not in source
