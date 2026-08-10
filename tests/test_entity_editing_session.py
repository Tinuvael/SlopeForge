from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from application.ports.assessment_state import AssessmentStateSnapshot
from application.services.entity_editing import AssessmentEditingSession
from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision
from domain.assessment.evaluation import AssessmentAreaEvaluationService
from domain.blasting.entities import BlastEvent, BlastEventGeometryRevision
from domain.geometry.types import PlanPoint, PlanPolygon


class MemoryPersistence:
    def __init__(self, state, *, fail=False):
        self.state = state
        self.fail = fail
        self.saves = 0

    def load(self, domain_id):
        return AssessmentStateSnapshot(domain_id, 7, None, self.state)

    def save(self, domain_id, state):
        self.saves += 1
        if self.fail:
            raise RuntimeError("database unavailable")
        return AssessmentStateSnapshot(domain_id, 7, 42, deepcopy(state))


def entities():
    polygon = PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 5),
                           PlanPoint(0, 5), PlanPoint(0, 0)))
    event = BlastEvent("BE-1", "Block", "production", date.today(), 100)
    event.geometry_revisions.append(BlastEventGeometryRevision(
        "BEG-1", event.id, 1, datetime.now(timezone.utc), "event.csv", [], polygon, 100, True))
    event.active_geometry_revision_id = "BEG-1"
    geometry = AssessmentAreaGeometryRevision(
        "AAG-1", "AA-1", 1, datetime.now(timezone.utc), "DATASET-1",
        polygon, polygon, 90, 110, ())
    area = AssessmentArea("AA-1", "Wall", date.today(), [geometry], geometry.id)
    return event, area


def session(*, fail=False, can_edit=True):
    event, area = entities()
    persistence = MemoryPersistence(AssessmentDomainState(
        blast_events=[event], assessment_areas=[area]), fail=fail)
    return AssessmentEditingSession(
        persistence, 3, actor_id=11, can_edit=can_edit), persistence, event, area


def test_card_draft_creation_save_and_existing_revision_copy():
    editing, persistence, event, _ = session()
    card, draft = editing.technical_card_draft(event)
    assert editing.state.technical_cards == [card]
    assert draft.geometry_revision_id == event.active_geometry_revision_id
    editing.save_technical_card(card, draft, "draft")
    assert len(card.revisions) == 1
    assert card.active_revision_id == card.revisions[0].id
    assert persistence.saves == 1 and editing.workspace_id == 42

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
    owner, _ = editing.prepare_evaluation_attachment_owner(area)
    editing.save()
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
