from datetime import date
from pathlib import Path

import pytest

from prototype_2d.blast_event_service import BlastEventService
from prototype_2d.domain import AssessmentDomainState


def _widget(state=None, save_callback=lambda: None, storage_path=None):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from ui.prototype_2d.assessment_workspace import AssessmentWorkspaceWidget

    app = QApplication.instance() or QApplication([])
    return AssessmentWorkspaceWidget(
        state if state is not None else AssessmentDomainState(), storage_path, save_callback
    ), app


def test_workspace_uses_injected_state_and_persistence():
    state = AssessmentDomainState()
    saves = []
    widget, app = _widget(state, lambda: saves.append(state))
    saved_signals = []
    widget.state_saved.connect(lambda: saved_signals.append(True))

    widget._save()

    assert widget.state is state
    assert saves == [state]
    assert saved_signals == [True]
    widget.close()
    assert app


def test_workspace_does_not_import_json_storage_functions():
    source = Path("ui/prototype_2d/assessment_workspace.py").read_text(encoding="utf-8")
    assert "load_blast_event_state" not in source
    assert "save_blast_event_state" not in source


def test_workspace_does_not_emit_saved_when_callback_fails():
    def fail():
        raise RuntimeError("disk failure")

    widget, app = _widget(save_callback=fail)
    saved_signals = []
    widget.state_saved.connect(lambda: saved_signals.append(True))
    with pytest.raises(RuntimeError, match="disk failure"):
        widget._save()
    assert saved_signals == []
    widget.close()
    assert app


def test_navigation_selects_active_and_archived_events(tmp_path):
    def csv(path):
        path.write_text(
            "XP,YP,ZP,SID,PTN\n0,0,620,top,1\n10,0,620,top,2\n"
            "10,10,620,top,3\n0,0,620,top,4\n",
            encoding="utf-8",
        )

    state = AssessmentDomainState()
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    csv(first_path); csv(second_path)
    service = BlastEventService(state)
    active = service.create_event(name="Active", event_type="production", event_date=date.today(), elevation=620, csv_path=first_path)
    archived = service.create_event(name="Archived", event_type="production", event_date=date.today(), elevation=620, csv_path=second_path)
    archived.archive()
    widget, app = _widget(state)

    assert widget.open_blast_event(active.id)
    assert widget.selected_event is active and widget.filter_combo.currentIndex() == 0
    assert widget.open_blast_event(archived.id)
    assert widget.selected_event is archived and widget.filter_combo.currentIndex() == 1
    assert not widget.open_blast_event("missing")
    widget.close()
    assert app


def test_active_workflow_can_be_cancelled():
    widget, app = _widget()
    widget.workflow_state = "DRAWING"
    assert widget.has_active_workflow()
    assert widget.cancel_active_workflow()
    assert not widget.has_active_workflow()
    assert not widget.cancel_active_workflow()
    widget.close()
    assert app
