from datetime import date
from pathlib import Path

import pytest

from prototype_2d.blast_event_service import BlastEventService
from prototype_2d.domain import AssessmentDomainState


def _widget(state=None, save_callback=lambda: None, storage_path=None, read_only=False,
            persist_dataset_callback=None, set_active_dataset_callback=None):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from ui.prototype_2d.assessment_workspace import AssessmentWorkspaceWidget

    app = QApplication.instance() or QApplication([])
    return AssessmentWorkspaceWidget(
        state if state is not None else AssessmentDomainState(), storage_path, save_callback,
        read_only=read_only, persist_dataset_callback=persist_dataset_callback,
        set_active_dataset_callback=set_active_dataset_callback,
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


def _project_state(tmp_path):
    from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService

    source = tmp_path / "project.csv"
    source.write_text(
        "XP,YP,ZP,SID,PTN\n0,2,600,lo,1\n10,2,600,lo,2\n"
        "0,8,620,hi,1\n10,8,620,hi,2\n",
        encoding="utf-8",
    )
    state = AssessmentDomainState()
    ProjectLinesDatasetService(state).import_dataset(source)
    return state


def _area(state, *, archived=False):
    from prototype_2d.assessment_area_service import AssessmentAreaService
    from prototype_2d.domain import PlanPoint, PlanPolygon

    polygon = PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10),
                           PlanPoint(0, 10), PlanPoint(0, 0)))
    service = AssessmentAreaService(state)
    area = service.create_area(
        name="Area", assessment_date=date.today(), selection_polygon=polygon,
        selected_fragments=service.generate_candidates(polygon),
    )
    if archived:
        area.archive()
    return area


def test_mutation_signals_follow_successful_callback():
    order = []
    widget, app = _widget(save_callback=lambda: order.append("callback"))
    widget.state_changed.connect(lambda: order.append("changed"))
    widget.state_saved.connect(lambda: order.append("saved"))
    widget._save()
    assert order == ["callback", "changed", "saved"]
    widget.deleteLater(); assert app


def test_failed_callback_emits_neither_success_signal():
    def fail():
        raise RuntimeError("no space")
    widget, app = _widget(save_callback=fail)
    emitted = []
    widget.state_changed.connect(lambda: emitted.append("changed"))
    widget.state_saved.connect(lambda: emitted.append("saved"))
    with pytest.raises(RuntimeError):
        widget._save()
    assert emitted == []
    widget.deleteLater(); assert app


def test_save_now_only_reports_persistence():
    order = []
    widget, app = _widget(save_callback=lambda: order.append("callback"))
    widget.state_changed.connect(lambda: order.append("changed"))
    widget.state_saved.connect(lambda: order.append("saved"))
    widget.save_now()
    assert order == ["callback", "saved"]
    widget.deleteLater(); assert app


def test_read_only_save_now_is_a_silent_noop():
    state = AssessmentDomainState()
    saves = []
    widget, app = _widget(state, lambda: saves.append(True), read_only=True)
    emitted = []
    widget.state_changed.connect(lambda: emitted.append("changed"))
    widget.state_saved.connect(lambda: emitted.append("saved"))

    widget.save_now()

    assert saves == []
    assert emitted == []
    assert widget.state is state
    widget.deleteLater(); assert app


def test_assessment_area_navigation_active_archived_and_missing(tmp_path):
    state = _project_state(tmp_path)
    active = _area(state)
    archived = _area(state, archived=True)
    widget, app = _widget(state)
    assert widget.open_assessment_area(active.id)
    assert widget.mode_tabs.currentIndex() == 1
    assert widget.area_filter_combo.currentIndex() == 0
    assert widget.selected_area is active
    assert widget.open_assessment_area(archived.id)
    assert widget.area_filter_combo.currentIndex() == 1
    assert widget.selected_area is archived
    assert not widget.open_assessment_area("unknown")
    widget.deleteLater(); assert app


def test_dataset_navigation_activation_persistence_and_toolbar(tmp_path):
    from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
    state = _project_state(tmp_path)
    first = state.datasets[0]
    second_source = tmp_path / "second-project.csv"
    second_source.write_text("XP,YP,ZP,SID,PTN\n0,0,640,x,1\n1,0,640,x,2\n", encoding="utf-8")
    second, _ = ProjectLinesDatasetService(state).import_dataset(second_source)
    saves = []
    widget, app = _widget(state, lambda: saves.append(True))
    assert not widget.open_dataset("unknown")
    assert widget.open_dataset(first.id)
    assert state.active_dataset() is first and saves == [True]
    assert first.name in widget.dataset_label.text()
    assert widget.open_dataset(first.id) and saves == [True]
    assert widget.open_dataset(second.id)
    assert state.active_dataset() is second and saves == [True, True]
    widget.deleteLater(); assert app


def test_refresh_workspace_preserves_and_clears_event_selection(tmp_path):
    state = AssessmentDomainState()
    source = tmp_path / "event.csv"
    source.write_text("XP,YP,ZP,SID,PTN\n0,0,620,t,1\n10,0,620,t,2\n10,10,620,t,3\n0,0,620,t,4\n", encoding="utf-8")
    active = BlastEventService(state).create_event(name="A", event_type="production", event_date=date.today(), elevation=620, csv_path=source)
    archived = BlastEventService(state).create_event(name="B", event_type="production", event_date=date.today(), elevation=620, csv_path=source)
    archived.archive()
    widget, app = _widget(state)
    counts = (len(state.blast_events), sum(len(e.geometry_revisions) for e in state.blast_events))
    for event in (active, archived):
        assert widget.open_blast_event(event.id)
        widget.refresh_workspace()
        assert widget.selected_event is event
    state.blast_events.remove(archived)
    widget.refresh_workspace()
    assert widget.selected_event is None
    assert (len(state.blast_events), sum(len(e.geometry_revisions) for e in state.blast_events)) == (counts[0] - 1, counts[1] - len(archived.geometry_revisions))
    widget.deleteLater(); assert app


def test_refresh_workspace_preserves_and_clears_area_selection(tmp_path):
    state = _project_state(tmp_path)
    area = _area(state)
    widget, app = _widget(state)
    assert widget.open_assessment_area(area.id)
    revision_count = len(area.geometry_revisions)
    widget.refresh_workspace()
    assert widget.selected_area is area and len(area.geometry_revisions) == revision_count
    state.assessment_areas.remove(area)
    widget.refresh_workspace()
    assert widget.selected_area is None
    widget.deleteLater(); assert app


def test_technical_card_save_uses_injected_callback(tmp_path):
    state = AssessmentDomainState()
    source = tmp_path / "event-card.csv"
    source.write_text("XP,YP,ZP,SID,PTN\n0,0,620,t,1\n10,0,620,t,2\n10,10,620,t,3\n0,0,620,t,4\n", encoding="utf-8")
    event = BlastEventService(state).create_event(name="A", event_type="production", event_date=date.today(), elevation=620, csv_path=source)
    saves = []
    widget, app = _widget(state, lambda: saves.append(True))
    card, draft = widget.technical_card_service.edit_or_create(event)
    widget._save_technical_card(card, draft, "draft")
    assert saves == [True] and card.active_revision() is not None
    widget.deleteLater(); assert app


def test_wall_assessment_save_and_failed_save_rollback(tmp_path):
    state = _project_state(tmp_path)
    area = _area(state)
    saves = []
    widget, app = _widget(state, lambda: saves.append(True))
    evaluation, draft = widget.evaluation_service.new_evaluation(area)
    widget._save_wall_assessment(evaluation, draft, "draft")
    assert saves == [True] and evaluation in state.evaluations
    old_count, old_active = len(evaluation.revisions), evaluation.active_revision_id

    def fail():
        raise RuntimeError("write failed")
    widget._save_callback = fail
    emitted = []
    widget.state_changed.connect(lambda: emitted.append("changed"))
    widget.state_saved.connect(lambda: emitted.append("saved"))
    with pytest.raises(RuntimeError):
        widget._save_wall_assessment(evaluation, draft, "draft")
    assert len(evaluation.revisions) == old_count
    assert evaluation.active_revision_id == old_active
    assert evaluation in state.evaluations
    assert emitted == []

    new_evaluation, new_draft = widget.evaluation_service.new_evaluation(area)
    with pytest.raises(RuntimeError):
        widget._save_wall_assessment(new_evaluation, new_draft, "draft")
    assert new_evaluation not in state.evaluations
    assert new_evaluation.revisions == [] and new_evaluation.active_revision_id is None
    assert emitted == []
    widget.deleteLater(); assert app


def test_read_only_blocks_direct_mutating_methods(tmp_path):
    state = _project_state(tmp_path)
    area = _area(state)
    source = tmp_path / "event-readonly.csv"
    source.write_text("XP,YP,ZP,SID,PTN\n0,0,620,t,1\n10,0,620,t,2\n10,10,620,t,3\n0,0,620,t,4\n", encoding="utf-8")
    event = BlastEventService(state).create_event(name="A", event_type="production", event_date=date.today(), elevation=620, csv_path=source)
    widget, app = _widget(state, read_only=True)
    widget.selected_event = event
    widget.selected_area = area

    mutating_calls = [
        lambda: widget._save(),
        lambda: widget.import_project_lines(),
        lambda: widget.create_event(),
        lambda: widget.reimport_geometry(),
        lambda: widget.toggle_archive(),
        lambda: widget.toggle_area_archive(),
        lambda: widget.refresh_area_links(),
        lambda: widget.start_area_drawing(),
        lambda: widget.enter_refinement(),
        lambda: widget.confirm_refined_polygon(),
        lambda: widget.edit_area_boundaries(),
        lambda: widget._save_technical_card(type("Card", (), {"save_revision": lambda self, revision, status: None})(), object(), "draft"),
    ]
    for call in mutating_calls:
        with pytest.raises(PermissionError):
            call()

    assert widget.open_blast_event(event.id)
    assert widget.open_assessment_area(area.id)
    widget.refresh_workspace()
    widget.deleteLater(); assert app


def test_read_only_open_dataset_blocks_active_dataset_change(tmp_path):
    from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
    state = _project_state(tmp_path)
    first = state.datasets[0]
    second_source = tmp_path / "second-readonly.csv"
    second_source.write_text("XP,YP,ZP,SID,PTN\n0,0,640,x,1\n1,0,640,x,2\n", encoding="utf-8")
    second, _ = ProjectLinesDatasetService(state).import_dataset(second_source)
    widget, app = _widget(state, read_only=True)

    assert state.active_dataset() is second
    with pytest.raises(PermissionError):
        widget.open_dataset(first.id)
    assert state.active_dataset() is second
    widget.deleteLater(); assert app


def test_attachment_service_uses_injected_storage_path(tmp_path):
    storage = tmp_path / "nested" / "workspace.json"
    widget, app = _widget(storage_path=storage)
    assert widget.attachment_service.storage_path == storage
    assert widget.attachment_service.owner_folder("blast_event", "BE-1", create=False) == tmp_path / "nested" / "files" / "blast_events" / "BE-1"
    assert widget.attachment_service.owner_folder("assessment_evaluation", "EV-1", create=False) == tmp_path / "nested" / "files" / "assessments" / "EV-1"
    widget.deleteLater(); assert app


def test_dataset_activation_uses_focused_callback_and_rolls_back_on_failure(tmp_path):
    from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
    state = _project_state(tmp_path)
    first = state.datasets[0]
    source = tmp_path / "second-callback.csv"
    source.write_text("XP,YP,ZP,SID,PTN\n0,0,640,x,1\n1,0,640,x,2\n", encoding="utf-8")
    second, _ = ProjectLinesDatasetService(state).import_dataset(source)
    calls = []
    widget, app = _widget(state, set_active_dataset_callback=lambda value: calls.append(value))
    widget._activate_dataset(first.id)
    assert calls == [first.id]
    assert state.active_dataset().id == first.id

    widget._set_active_dataset_callback = lambda _value: (_ for _ in ()).throw(RuntimeError("db"))
    with pytest.raises(RuntimeError, match="db"):
        widget._activate_dataset(second.id)
    assert state.active_dataset().id == first.id
    widget.deleteLater(); assert app
