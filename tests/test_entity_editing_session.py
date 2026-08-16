from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from application.ports.assessment_state import AssessmentStateSnapshot
from application.ports.domain_version import DomainWriteResult
from application.services.entity_editing import AssessmentEditingSession
from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.entities import AssessmentArea, AssessmentEventLink
from tests.assessment_boundary_fixtures import boundary_from_polygon, geometry_revision
from domain.assessment.evaluation import AssessmentAreaEvaluationService
from domain.blasting.entities import BlastEvent, BlastEventGeometryRevision
from domain.geometry.types import PlanPoint, PlanPolygon


class MemoryPersistence:
    def __init__(self, state, *, fail=False):
        self.state = state
        self.fail = fail
        self.saves = 0

    def load(self, domain_id):
        return AssessmentStateSnapshot(domain_id, 7, self.state, self.saves)

    def __getattr__(self, name):
        if name.startswith(("persist_", "append_", "synchronize_", "add_", "update_", "delete_")):
            def focused(domain_id, expected_version, *args):
                if self.fail:
                    raise RuntimeError("database unavailable")
                self.saves += 1
                return DomainWriteResult(expected_version + 1)
            return focused
        raise AttributeError(name)


def entities():
    polygon = PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 5),
                           PlanPoint(0, 5), PlanPoint(0, 0)))
    event = BlastEvent("BE-1", "Block", "production", date.today(), 100)
    event.geometry_revisions.append(BlastEventGeometryRevision(
        "BEG-1", event.id, 1, datetime.now(timezone.utc), "event.csv", [], polygon, 100, True))
    event.active_geometry_revision_id = "BEG-1"
    geometry = geometry_revision(
        "AAG-1", "AA-1", 1, datetime.now(timezone.utc), polygon,
        dataset_id="DATASET-1", minimum=90, maximum=110)
    area = AssessmentArea("AA-1", "Wall", date.today(), [geometry], geometry.id)
    return event, area


def session(*, fail=False, can_edit=True):
    event, area = entities()
    persistence = MemoryPersistence(AssessmentDomainState(
        blast_events=[event], assessment_areas=[area]), fail=fail)
    return AssessmentEditingSession(
        persistence, 3, actor_id=11, can_edit=can_edit, writes=persistence), persistence, event, area


def test_card_draft_creation_save_and_existing_revision_copy():
    editing, persistence, event, _ = session()
    card, draft = editing.technical_card_draft(event)
    assert editing.state.technical_cards == [card]
    assert draft.geometry_revision_id == event.active_geometry_revision_id
    editing.save_technical_card(card, draft, "draft")
    assert len(card.revisions) == 1
    assert card.active_revision_id == card.revisions[0].id
    assert persistence.saves == 1 and editing.expected_version == 1

    source = card.active_revision()
    _, edited = editing.technical_card_draft(event)
    assert edited is not source
    edited.common_parameters.comments = "not saved"
    assert source.common_parameters.comments == ""


def test_card_persistence_failure_restores_existing_revision_and_active_id():
    editing, persistence, event, _ = session()
    card, draft = editing.technical_card_draft(event)
    editing.save_technical_card(card, draft, "draft")
    old_revisions = list(card.revisions)
    old_active = card.active_revision_id
    persistence.fail = True
    with pytest.raises(RuntimeError, match="database unavailable"):
        editing.save_technical_card(card, deepcopy(card.active_revision()), "draft")
    assert card.revisions == old_revisions
    assert card.active_revision_id == old_active


def test_first_card_save_failure_leaves_reusable_empty_card_without_phantom_revision():
    editing, _, event, _ = session(fail=True)
    card, draft = editing.technical_card_draft(event)
    with pytest.raises(RuntimeError):
        editing.save_technical_card(card, draft, "draft")
    assert card in editing.state.technical_cards
    assert card.revisions == [] and card.active_revision_id is None
    reused, retry = editing.technical_card_draft(event)
    assert reused is card and retry.technical_card_id == card.id
    assert draft.common_parameters is not None  # the editor-owned input remains usable


def test_evaluation_open_is_transient_then_first_save_persists_owner_and_revision():
    editing, persistence, _, area = session()
    evaluation, draft = editing.evaluation_draft(area)
    assert evaluation not in editing.state.evaluations and persistence.saves == 0
    editing.save_evaluation(evaluation, draft, "draft")
    assert editing.state.evaluations == [evaluation]
    assert len(evaluation.revisions) == 1 and evaluation.active_revision_id


def test_evaluation_failure_restores_graph_for_first_and_existing_save():
    editing, persistence, _, area = session()
    evaluation, draft = editing.evaluation_draft(area)
    persistence.fail = True
    with pytest.raises(RuntimeError):
        editing.save_evaluation(evaluation, draft, "draft")
    assert evaluation not in editing.state.evaluations
    assert evaluation.revisions == [] and evaluation.active_revision_id is None

    persistence.fail = False
    editing.save_evaluation(evaluation, draft, "draft")
    old_revisions, old_active = list(evaluation.revisions), evaluation.active_revision_id
    persistence.fail = True
    with pytest.raises(RuntimeError):
        editing.save_evaluation(evaluation, deepcopy(evaluation.active_revision()), "draft")
    assert evaluation.revisions == old_revisions and evaluation.active_revision_id == old_active


def test_historical_completed_evaluation_draft_reads_separate_stored_indices_without_recalculation():
    editing, _, _, area = session()
    evaluation, draft = editing.evaluation_draft(area)
    editing.save_evaluation(evaluation, draft, "draft")
    stored = evaluation.active_revision()
    # Deliberately use distinct persisted values. Opening history must not run the
    # current matrix or linked-event calculation over them.
    stored.status = "completed"
    stored.design_achievement_index = 0.23
    stored.face_condition_index = 0.87
    stored.result_quadrant = "stored_historical_result"
    _, historical = editing.evaluation_draft(area)
    assert historical.design_achievement_index == 0.23
    assert historical.face_condition_index == 0.87
    assert historical.result_quadrant == "stored_historical_result"
    assert historical is not stored


def test_auto_draft_matrix_refreshes_for_confirmed_contour_and_reverse():
    editing,persistence,_,area=session(); evaluation,draft=editing.evaluation_draft(area); editing.save_evaluation(evaluation,draft,"draft")
    stored=deepcopy(evaluation.active_revision()); contour=BlastEvent("BE-C","Contour","contour",date.today(),100); editing.state.blast_events.append(contour)
    link=AssessmentEventLink(contour.id,"BEG-C","confirmed","automatic",assessment_area_geometry_revision_id=area.active_geometry_revision_id); area.event_links.append(link)
    _,controlled=editing.evaluation_draft(area)
    assert controlled.matrix_template_id=="controlled_blasting_v1"
    assert "visible_drillhole_traces" in {r.criterion_id for r in controlled.criterion_results}
    assert evaluation.active_revision().to_dict()==stored.to_dict() and persistence.saves==1
    editing.save_evaluation(evaluation,controlled,"draft")
    link.status="excluded"; _,plain=editing.evaluation_draft(area)
    assert plain.matrix_template_id=="no_controlled_blasting_v1"


def test_manual_matrix_draft_is_not_auto_replaced():
    editing,_,_,area=session(); evaluation,draft=editing.evaluations.new_evaluation(area,"controlled_blasting_v1","Manual choice"); editing.save_evaluation(evaluation,draft,"draft")
    assert evaluation.active_revision().controlled_blasting_detection_source=="manual_override"
    _,reopened=editing.evaluation_draft(area)
    assert reopened.matrix_template_id=="controlled_blasting_v1" and reopened.controlled_blasting_detection_source=="manual_override"


def test_lazy_owner_rollback_only_removes_new_empty_owner():
    editing, persistence, _, area = session()
    transient, _ = editing.evaluation_draft(area)
    owner, rollback = editing.prepare_evaluation_attachment_owner(area, transient)
    assert owner is transient and editing.state.evaluations == [owner]
    assert persistence.saves == 0
    rollback()
    assert editing.state.evaluations == []

    editing.state.evaluations.append(owner)
    existing, existing_rollback = editing.prepare_evaluation_attachment_owner(area)
    assert existing is owner and existing_rollback is None
    assert editing.state.evaluations == [owner]


def test_successful_owner_save_keeps_owner_and_viewer_mutations_are_rejected():
    editing, persistence, event, area = session()
    owner = editing.ensure_evaluation_owner(area)
    assert owner in editing.state.evaluations and persistence.saves == 1

    viewer, _, viewer_event, viewer_area = session(can_edit=False)
    card, card_draft = viewer.technical_card_draft(viewer_event)
    evaluation, evaluation_draft = viewer.evaluation_draft(viewer_area)
    with pytest.raises(PermissionError):
        viewer.save_technical_card(card, card_draft, "draft")
    with pytest.raises(PermissionError):
        viewer.save_evaluation(evaluation, evaluation_draft, "draft")
    with pytest.raises(PermissionError):
        viewer.prepare_evaluation_attachment_owner(viewer_area)


def test_area_and_contour_archive_restore_and_failure_rollback():
    editing, persistence, _, area = session()
    contour = BlastEvent("BE-C", "Contour", "contour", date.today(), 100)
    editing.state.blast_events.append(contour)
    editing.set_assessment_area_archived(area, True)
    editing.set_contour_event_archived(contour, True)
    assert area.is_archived and contour.is_archived and persistence.saves == 2
    editing.set_assessment_area_archived(area, False)
    editing.set_contour_event_archived(contour, False)
    assert not area.is_archived and not contour.is_archived

    area.archive("original")
    old = (area.is_archived, area.archived_at, area.archive_reason)
    persistence.fail = True
    with pytest.raises(RuntimeError):
        editing.set_assessment_area_archived(area, False)
    assert (area.is_archived, area.archived_at, area.archive_reason) == old
    with pytest.raises(RuntimeError):
        editing.set_contour_event_archived(contour, True)
    assert not contour.is_archived and contour.archived_at is None


def test_archive_and_reimport_permissions_and_contour_type_are_enforced(tmp_path):
    viewer, persistence, event, area = session(can_edit=False)
    with pytest.raises(PermissionError):
        viewer.set_assessment_area_archived(area, True)
    with pytest.raises(PermissionError):
        viewer.reimport_blast_event_geometry(event, tmp_path / "unused.csv")
    assert persistence.saves == 0 and not area.is_archived
    editing, _, production, _ = session()
    with pytest.raises(ValueError, match="contour"):
        editing.set_contour_event_archived(production, True)


def test_reimport_success_and_persistence_failure_restore_live_geometry():
    editing, persistence, event, _ = session()
    path = "tests/fixtures/production_two_closed_levels.csv"
    original = event.geometry_revisions[0]
    added = editing.reimport_blast_event_geometry(event, path)
    assert persistence.saves == 1 and added.revision_number == 2
    assert not original.is_active and added.is_active
    before = list(event.geometry_revisions)
    persistence.fail = True
    with pytest.raises(RuntimeError):
        editing.reimport_blast_event_geometry(event, path)
    assert event.geometry_revisions == before
    assert event.active_geometry_revision_id == added.id
    assert [revision.is_active for revision in before] == [False, True]


def test_link_commands_save_once_and_restore_exact_objects_on_failure():
    editing, persistence, event, area = session()
    result = editing.refresh_event_link_suggestions(area)
    assert result.suggestions_added == 1 and persistence.saves == 1
    link = area.event_links[0]
    editing.confirm_event_link(area, link.id)
    assert link.status == "confirmed" and persistence.saves == 2
    editing.exclude_event_link(area, link.id)
    assert link.status == "excluded" and persistence.saves == 3
    editing.restore_event_link(area, link.id)
    assert link.status == "suggested" and persistence.saves == 4
    original_links = list(area.event_links)
    persistence.fail = True
    with pytest.raises(RuntimeError):
        editing.confirm_event_link(area, link.id)
    assert area.event_links == original_links and area.event_links[0] is link
    assert link.status == "suggested"


def geometry_session(tmp_path, *, fail=False, can_edit=True):
    from application.services.project_lines import ProjectLinesDatasetService
    state = AssessmentDomainState()
    source = tmp_path / "lines.csv"
    source.write_text("XP,YP,ZP,SID,PTN\n0,2,90,lo,1\n10,2,90,lo,2\n0,8,110,hi,1\n10,8,110,hi,2\n", encoding="utf-8")
    ProjectLinesDatasetService(state).import_dataset(source)
    persistence = MemoryPersistence(state, fail=fail)
    editing = AssessmentEditingSession(persistence, 3, actor_id=11, can_edit=can_edit, writes=persistence)
    polygon = PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10), PlanPoint(0, 10), PlanPoint(0, 0)))
    boundary = boundary_from_polygon(polygon, dataset_id=state.active_dataset().id, line_id="lo", minimum=90, maximum=110)
    return editing, persistence, polygon, boundary


def test_geometry_commit_create_and_revision_history(tmp_path):
    editing, persistence, polygon, boundary = geometry_session(tmp_path)
    created = editing.save_assessment_area_geometry(name="Wall", assessment_date=date.today(),
        boundary=boundary)
    area = editing.state.assessment_areas[0]; first = area.geometry_revisions[0]
    assert created.created and created.area_id == area.id and persistence.saves == 1
    first_snapshot = deepcopy(first.to_dict())
    revised_polygon = PlanPolygon((PlanPoint(1, 0), PlanPoint(9, 0), PlanPoint(9, 10),
                                   PlanPoint(1, 10), PlanPoint(1, 0)))
    revised_boundary = boundary_from_polygon(revised_polygon, dataset_id=editing.state.active_dataset().id,
                                             line_id="lo", minimum=90, maximum=110)
    revised = editing.save_assessment_area_geometry(assessment_area_id=area.id,
        boundary=revised_boundary)
    assert not revised.created and editing.state.assessment_areas[0] is area
    assert len(area.geometry_revisions) == 2 and area.geometry_revisions[0] is first
    assert area.active_geometry_revision_id == area.geometry_revisions[1].id
    assert first.to_dict() == first_snapshot and persistence.saves == 2


def test_geometry_commit_link_failure_is_partial_and_save_failure_rolls_back(tmp_path, monkeypatch):
    editing, persistence, polygon, boundary = geometry_session(tmp_path)
    monkeypatch.setattr(editing.links, "refresh_suggestions", lambda area: (_ for _ in ()).throw(RuntimeError("scan failed")))
    result = editing.save_assessment_area_geometry(name="Wall", assessment_date=date.today(),
        boundary=boundary)
    assert result.link_refresh_result is None and result.link_refresh_warning == "scan failed"
    area = editing.state.assessment_areas[0]; first = area.geometry_revisions[0]
    persistence.fail = True
    with pytest.raises(RuntimeError, match="database unavailable"):
        editing.save_assessment_area_geometry(assessment_area_id=area.id,
            boundary=boundary)
    assert editing.state.assessment_areas[0] is area
    assert area.geometry_revisions == [first] and area.active_geometry_revision_id == first.id


def test_geometry_commit_new_failure_and_viewer_do_not_mutate(tmp_path):
    editing, _, polygon, boundary = geometry_session(tmp_path, fail=True)
    with pytest.raises(RuntimeError):
        editing.save_assessment_area_geometry(name="Wall", assessment_date=date.today(),
            boundary=boundary)
    assert editing.state.assessment_areas == []
    viewer, _, polygon, boundary = geometry_session(tmp_path, can_edit=False)
    with pytest.raises(PermissionError):
        viewer.save_assessment_area_geometry(name="Wall", assessment_date=date.today(),
            boundary=boundary)
    assert viewer.state.assessment_areas == []


def test_geometry_link_scan_failure_after_real_partial_mutation_restores_links(tmp_path, monkeypatch):
    """refresh_suggestions cleans links before evaluation; that partial edit must not leak."""
    from domain.assessment.entities import AssessmentEventLink
    editing, persistence, polygon, boundary = geometry_session(tmp_path)
    event, _unused = entities()
    editing.state.blast_events.append(event)
    editing.save_assessment_area_geometry(name="Wall", assessment_date=date.today(),
        boundary=boundary)
    area = editing.state.assessment_areas[0]
    historical = AssessmentEventLink("OLD", "OLD-R1", "confirmed", "manual",
        id="historical", assessment_area_geometry_revision_id=area.active_geometry_revision_id)
    area.event_links[:] = [historical]
    original_revise = editing.areas.revise_area
    current = None

    def revise_with_disposable_link(*args, **kwargs):
        nonlocal current
        revision = original_revise(*args, **kwargs)
        current = AssessmentEventLink("DISPOSABLE", "D-R1", "suggested", "automatic",
            id="disposable", assessment_area_geometry_revision_id=area.active_geometry_revision_id)
        area.event_links.append(current)
        return revision

    monkeypatch.setattr(editing.areas, "revise_area", revise_with_disposable_link)
    calls = 0
    def fail_during_evaluation(_area, _event):
        nonlocal calls
        calls += 1
        raise RuntimeError("evaluation failed after cleanup")
    monkeypatch.setattr(editing.links, "evaluate_event", fail_during_evaluation)

    result = editing.save_assessment_area_geometry(assessment_area_id=area.id,
        boundary=boundary)
    assert calls == 1 and result.link_refresh_warning == "evaluation failed after cleanup"
    assert area.event_links == [historical, current]
    assert area.event_links[0] is historical and area.event_links[1] is current
    assert historical.status == "confirmed" and current.status == "suggested"
    assert persistence.saves == 2


def test_geometry_persistence_failure_after_successful_link_refresh_restores_exact_graph(tmp_path):
    from domain.assessment.entities import AssessmentEventLink
    editing, persistence, polygon, boundary = geometry_session(tmp_path)
    editing.save_assessment_area_geometry(name="Wall", assessment_date=date.today(),
        boundary=boundary)
    area = editing.state.assessment_areas[0]
    old_revision = area.geometry_revisions[0]
    old_boundary = old_revision.boundary
    old_final = old_revision.final_geometry_frozen
    old_link = AssessmentEventLink("OLD", "OLD-R1", "excluded", "manual",
        id="old", assessment_area_geometry_revision_id=old_revision.id)
    area.event_links[:] = [old_link]
    before_evaluations = list(editing.state.evaluations)
    persistence.fail = True

    with pytest.raises(RuntimeError, match="database unavailable"):
        editing.save_assessment_area_geometry(assessment_area_id=area.id,
            boundary=boundary)

    assert editing.state.assessment_areas[0] is area
    assert area.geometry_revisions == [old_revision]
    assert area.active_geometry_revision_id == old_revision.id
    assert area.event_links == [old_link] and area.event_links[0] is old_link
    assert old_link.status == "excluded"
    assert old_revision.boundary is old_boundary
    assert old_revision.final_geometry_frozen is old_final
    assert editing.state.evaluations == before_evaluations
