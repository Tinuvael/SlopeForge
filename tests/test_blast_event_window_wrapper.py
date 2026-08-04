import pytest

from prototype_2d.domain import AssessmentDomainState


def _app():
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    return QApplication.instance() or QApplication([])


def _module():
    _app()
    return pytest.importorskip("ui.prototype_2d.blast_event_window", exc_type=ImportError)


def _close_event():
    QCloseEvent = pytest.importorskip("PySide6.QtGui", exc_type=ImportError).QCloseEvent
    return QCloseEvent()


def test_wrapper_loads_and_saves_exact_state(monkeypatch, tmp_path):
    module = _module()
    state = AssessmentDomainState()
    loaded = []
    saved = []
    monkeypatch.setattr(module, "load_blast_event_state", lambda path: loaded.append(path) or state)
    monkeypatch.setattr(module, "save_blast_event_state", lambda value, path: saved.append((value, path)))
    app = _app()
    path = tmp_path / "state.json"
    window = module.BlastEventWindow(storage_path=path)
    assert loaded == [path]
    assert window.workspace.state is state
    window.workspace.save_now()
    assert saved == [(state, path)]
    for name in ("open_blast_event", "open_assessment_area", "open_dataset", "refresh_workspace"):
        assert callable(getattr(window, name))
    window.deleteLater(); assert app


def test_normal_close_persists_then_emits_closed(monkeypatch):
    module = _module()
    state = AssessmentDomainState(); saved = []; closed = []
    monkeypatch.setattr(module, "load_blast_event_state", lambda path: state)
    monkeypatch.setattr(module, "save_blast_event_state", lambda value, path: saved.append(value))
    app = _app(); window = module.BlastEventWindow()
    window.closed.connect(lambda: closed.append(True))
    event = _close_event(); window.closeEvent(event)
    assert saved == [state] and closed == [True] and event.isAccepted()
    window.deleteLater(); assert app


def test_close_persistence_failure_keeps_window_open(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "load_blast_event_state", lambda path: AssessmentDomainState())
    monkeypatch.setattr(module, "save_blast_event_state", lambda value, path: (_ for _ in ()).throw(RuntimeError("disk")))
    messages = []
    monkeypatch.setattr(module.QMessageBox, "critical", lambda *args: messages.append(args))
    app = _app(); window = module.BlastEventWindow(); closed = []
    window.closed.connect(lambda: closed.append(True))
    event = _close_event(); window.closeEvent(event)
    assert not event.isAccepted() and closed == [] and messages
    assert "Не удалось сохранить данные" in messages[0][2]
    window.deleteLater(); assert app


@pytest.mark.parametrize("answer, should_cancel, should_save", [
    ("cancel", False, False),
    ("discard", True, True),
])
def test_active_workflow_close_choices(monkeypatch, answer, should_cancel, should_save):
    module = _module()
    state = AssessmentDomainState(); saved = []
    monkeypatch.setattr(module, "load_blast_event_state", lambda path: state)
    monkeypatch.setattr(module, "save_blast_event_state", lambda value, path: saved.append(value))
    response = module.QMessageBox.StandardButton.Cancel if answer == "cancel" else module.QMessageBox.StandardButton.Discard
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *args: response)
    app = _app(); window = module.BlastEventWindow(); window.workspace.workflow_state = "DRAWING"
    event = _close_event(); window.closeEvent(event)
    assert (window.workspace.workflow_state == "IDLE") is should_cancel
    assert bool(saved) is should_save
    assert event.isAccepted() is should_save
    window.deleteLater(); assert app


def test_failed_save_after_discard_still_keeps_window_open(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "load_blast_event_state", lambda path: AssessmentDomainState())
    monkeypatch.setattr(module, "save_blast_event_state", lambda value, path: (_ for _ in ()).throw(RuntimeError("disk")))
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *args: module.QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(module.QMessageBox, "critical", lambda *args: None)
    app = _app(); window = module.BlastEventWindow(); window.workspace.workflow_state = "REFINING"
    closed = []; window.closed.connect(lambda: closed.append(True))
    event = _close_event(); window.closeEvent(event)
    assert window.workspace.workflow_state == "IDLE"
    assert not event.isAccepted() and closed == []
    window.deleteLater(); assert app
