"""Set-based collection of persisted facts consumed by the pure workflow policy."""
from __future__ import annotations

from sqlalchemy import select

from database import assessment_models as orm
from domain.blasting.workflow import derive_blast_workflow_state


def blast_workflow_states(session, events) -> dict[int, object]:
    events = list(events)
    if not events:
        return {}
    event_ids = [event.id for event in events]

    actual_dates: dict[int, str | None] = {}
    revisions = session.execute(
        select(orm.BlastEventTechnicalCard.blast_event_id,
               orm.BlastEventTechnicalCardRevision.payload_json)
        .join(orm.BlastEventTechnicalCardRevision)
        .where(orm.BlastEventTechnicalCard.blast_event_id.in_(event_ids),
               orm.BlastEventTechnicalCardRevision.is_active.is_(True))
    )
    for event_id, payload in revisions:
        actual_dates[event_id] = (payload or {}).get("actual_execution", {}).get("actual_blast_date")

    assessed_ids = set(session.scalars(
        select(orm.BlastEvent.id).distinct()
        .join(orm.BlastEventGeometryRevision)
        .join(orm.AssessmentEventLink,
              orm.AssessmentEventLink.blast_event_geometry_revision_id == orm.BlastEventGeometryRevision.id)
        .join(orm.AssessmentAreaGeometryRevision,
              orm.AssessmentAreaGeometryRevision.id == orm.AssessmentEventLink.assessment_area_geometry_revision_id)
        .join(orm.AssessmentArea,
              orm.AssessmentArea.id == orm.AssessmentAreaGeometryRevision.assessment_area_id)
        .join(orm.AssessmentAreaEvaluation,
              orm.AssessmentAreaEvaluation.assessment_area_id == orm.AssessmentArea.id)
        .join(orm.AssessmentAreaEvaluationRevision,
              orm.AssessmentAreaEvaluationRevision.evaluation_id == orm.AssessmentAreaEvaluation.id)
        .where(
            orm.BlastEvent.id.in_(event_ids),
            orm.BlastEventGeometryRevision.is_active.is_(True),
            orm.AssessmentAreaGeometryRevision.is_active.is_(True),
            orm.AssessmentEventLink.status == "confirmed",
            orm.AssessmentAreaEvaluation.is_archived.is_(False),
            orm.AssessmentAreaEvaluationRevision.is_active.is_(True),
            orm.AssessmentAreaEvaluationRevision.status == "completed",
            orm.AssessmentAreaEvaluationRevision.assessment_area_geometry_revision_id
            == orm.AssessmentAreaGeometryRevision.id,
        )
    ))
    return {event.id: derive_blast_workflow_state(
        event.event_date, actual_dates.get(event.id), event.id in assessed_ids)
        for event in events}
