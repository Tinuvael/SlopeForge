"""Pure, non-persisted workflow policies for Blast and Assessment entities."""
from __future__ import annotations

from datetime import date
from enum import StrEnum


class BlastWorkflowState(StrEnum):
    IN_PREPARATION = "in_preparation"
    PLANNED = "planned"
    BLASTED = "blasted"
    ASSESSED = "assessed"


class AssessmentProgressState(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


def derive_blast_workflow_state(
    planned_date: date | None,
    actual_date: date | str | None,
    has_current_completed_confirmed_assessment: bool,
) -> BlastWorkflowState:
    """Apply the single canonical precedence to persisted workflow facts."""
    if has_current_completed_confirmed_assessment:
        return BlastWorkflowState.ASSESSED
    if actual_date:
        return BlastWorkflowState.BLASTED
    if planned_date is not None:
        return BlastWorkflowState.PLANNED
    return BlastWorkflowState.IN_PREPARATION


def derive_assessment_progress_state(
    active_geometry_revision_id: str | None,
    evaluation_status: str | None,
    evaluation_geometry_revision_id: str | None,
) -> AssessmentProgressState:
    if (active_geometry_revision_id is not None
            and evaluation_status == "completed"
            and evaluation_geometry_revision_id == active_geometry_revision_id):
        return AssessmentProgressState.COMPLETED
    return AssessmentProgressState.IN_PROGRESS


WORKFLOW_LABELS = {
    BlastWorkflowState.IN_PREPARATION: "In preparation",
    BlastWorkflowState.PLANNED: "Planned",
    BlastWorkflowState.BLASTED: "Blasted",
    BlastWorkflowState.ASSESSED: "Assessed",
}

ASSESSMENT_PROGRESS_LABELS = {
    AssessmentProgressState.IN_PROGRESS: "In progress",
    AssessmentProgressState.COMPLETED: "Completed",
}


def assessment_progress_for(area, evaluation) -> AssessmentProgressState:
    revision = evaluation.active_revision() if evaluation else None
    return derive_assessment_progress_state(
        area.active_geometry_revision_id,
        revision.status if revision else None,
        revision.assessment_area_geometry_revision_id if revision else None,
    )


def blast_workflow_for(state, event) -> BlastWorkflowState:
    """Derive from a fully loaded persisted Domain snapshot."""
    card = next((item for item in state.technical_cards
                 if item.blast_event_id == event.id), None)
    card_revision = card.active_revision() if card else None
    actual_date = (card_revision.actual_execution.actual_blast_date
                   if card_revision else None)
    assessed = False
    for area in state.assessment_areas:
        if area.active_geometry_revision_id is None:
            continue
        evaluation = next((item for item in state.evaluations
                           if item.assessment_area_id == area.id and not item.is_archived), None)
        if assessment_progress_for(area, evaluation) != AssessmentProgressState.COMPLETED:
            continue
        if any(link.status == "confirmed"
               and link.assessment_area_geometry_revision_id == area.active_geometry_revision_id
               and link.blast_event_id == event.id
               and link.geometry_revision_id == event.active_geometry_revision_id
               for link in area.event_links):
            assessed = True
            break
    return derive_blast_workflow_state(event.event_date, actual_date, assessed)
