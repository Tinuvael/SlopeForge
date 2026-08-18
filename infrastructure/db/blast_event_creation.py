"""SQLAlchemy adapter for atomic Blast Event header creation."""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from application.ports.assessment_state import AssessmentStateSnapshot
from domain.blasting.entities import BlastEvent
from repositories.assessment_state_repository import AssessmentStateRepository
from repositories.audit_log_repository import AuditLogRepository
from infrastructure.db.assessment_writes import SqlAlchemyAssessmentWrites
from infrastructure.db.domain_version import guard_domain_versions


class SqlAlchemyBlastEventCreationPersistence:
    def __init__(self, session_factory: Callable[[], Session], *, failure_hook=None):
        self._session_factory = session_factory
        self._states = AssessmentStateRepository(session_factory)
        self._audit = AuditLogRepository(session_factory)
        self._failure_hook = failure_hook

    def load_state(self, domain_id: int) -> AssessmentStateSnapshot:
        loaded = self._states.load_for_domain(domain_id)
        return AssessmentStateSnapshot(loaded.domain_id, loaded.site_id,
                                       loaded.state, loaded.expected_version)

    def persist_event(self, domain_id: int, expected_version: int,
                      event: BlastEvent, actor_id: int | None) -> int:
        with self._session_factory.begin() as session:
            new_version = guard_domain_versions(session, {domain_id: expected_version})[domain_id]
            SqlAlchemyAssessmentWrites.insert_event_in_session(
                session, domain_id, event, created_by_user_id=actor_id)
            self._fail("after_event_flush")
            self._audit.add_entry(
                session,
                user_id=actor_id,
                action="create",
                entity_type="blast_event",
                entity_id=event.id,
                description=("Block created" if event.event_type == "production"
                             else "Contour Blast created"),
            )
            for revision in event.geometry_revisions:
                self._audit.add_entry(
                    session,
                    user_id=actor_id,
                    action="update",
                    entity_type="blast_event",
                    entity_id=event.id,
                    field_name="geometry_revision",
                    new_value=revision.id,
                    description="Geometry imported",
                )
            self._fail("before_commit")
            return new_version

    def _fail(self, stage: str) -> None:
        if self._failure_hook is not None:
            self._failure_hook(stage)
