from datetime import date
from types import SimpleNamespace

from domain.blasting.workflow import (
    AssessmentProgressState, BlastWorkflowState,
    derive_assessment_progress_state, derive_blast_workflow_state,
    blast_workflow_for,
)


def test_blast_workflow_precedence_and_demotion():
    planned = date(2026, 8, 20)
    assert derive_blast_workflow_state(None, None, False) == BlastWorkflowState.IN_PREPARATION
    assert derive_blast_workflow_state(planned, None, False) == BlastWorkflowState.PLANNED
    assert derive_blast_workflow_state(planned, "2026-08-21", False) == BlastWorkflowState.BLASTED
    assert derive_blast_workflow_state(planned, "2026-08-21", True) == BlastWorkflowState.ASSESSED
    assert derive_blast_workflow_state(planned, "2026-08-21", False) == BlastWorkflowState.BLASTED
    assert derive_blast_workflow_state(planned, None, False) == BlastWorkflowState.PLANNED
    assert derive_blast_workflow_state(None, None, False) == BlastWorkflowState.IN_PREPARATION


def test_assessment_progress_requires_completed_current_geometry():
    assert derive_assessment_progress_state("R1", None, None) == AssessmentProgressState.IN_PROGRESS
    assert derive_assessment_progress_state("R1", "draft", "R1") == AssessmentProgressState.IN_PROGRESS
    assert derive_assessment_progress_state("R1", "completed", "R1") == AssessmentProgressState.COMPLETED
    assert derive_assessment_progress_state("R2", "completed", "R1") == AssessmentProgressState.IN_PROGRESS
    assert derive_assessment_progress_state("R2", "completed", "R2") == AssessmentProgressState.COMPLETED


def _snapshot(*, event_date=date(2026, 8, 20), event_revision="E-R1", area_revision="A-R1", link_status="confirmed",
              link_event_revision="E-R1", evaluation_status="completed",
              evaluation_area_revision="A-R1", actual_date=None):
    event = SimpleNamespace(id="E", event_date=event_date,
                            active_geometry_revision_id=event_revision)
    link = SimpleNamespace(status=link_status,
        assessment_area_geometry_revision_id="A-R1", blast_event_id="E",
        geometry_revision_id=link_event_revision)
    area = SimpleNamespace(id="A", active_geometry_revision_id=area_revision,
                           event_links=[link])
    evaluation_revision = SimpleNamespace(status=evaluation_status,
        assessment_area_geometry_revision_id=evaluation_area_revision)
    evaluation = SimpleNamespace(assessment_area_id="A", is_archived=False,
                                 active_revision=lambda: evaluation_revision)
    card_revision = SimpleNamespace(status="draft", actual_execution=SimpleNamespace(
        actual_blast_date=actual_date))
    card = SimpleNamespace(blast_event_id="E", active_revision=lambda: card_revision)
    state = SimpleNamespace(technical_cards=[card], assessment_areas=[area],
                            evaluations=[evaluation])
    return state, event


def test_blast_workflow_progresses_while_technical_card_revision_stays_draft():
    state, event = _snapshot(
        event_date=None, actual_date=None, evaluation_status="draft", link_status="suggested"
    )
    assert state.technical_cards[0].active_revision().status == "draft"
    assert blast_workflow_for(state, event) == BlastWorkflowState.IN_PREPARATION

    event.event_date = date(2026, 8, 20)
    assert blast_workflow_for(state, event) == BlastWorkflowState.PLANNED

    state.technical_cards[0].active_revision().actual_execution.actual_blast_date = "2026-08-21"
    assert blast_workflow_for(state, event) == BlastWorkflowState.BLASTED

    area = state.assessment_areas[0]
    area.event_links[0].status = "confirmed"
    state.evaluations[0].active_revision().status = "completed"
    assert blast_workflow_for(state, event) == BlastWorkflowState.ASSESSED
    assert state.technical_cards[0].active_revision().status == "draft"


def test_assessed_requires_current_confirmed_link_and_current_completed_evaluation():
    state, event = _snapshot()
    assert blast_workflow_for(state, event) == BlastWorkflowState.ASSESSED
    for changes in (
        {"event_revision": "E-R2"},
        {"area_revision": "A-R2"},
        {"link_status": "suggested"},
        {"link_status": "excluded"},
        {"evaluation_status": "draft"},
        {"evaluation_area_revision": "A-R0"},
    ):
        state, event = _snapshot(actual_date="2026-08-21", **changes)
        assert blast_workflow_for(state, event) == BlastWorkflowState.BLASTED
