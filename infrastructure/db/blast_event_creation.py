"""SQLAlchemy adapter for atomic Blast Event header creation."""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from sqlalchemy.orm import Session

from application.ports.assessment_state import AssessmentStateSnapshot
from domain.blasting.entities import BlastEvent
from database.models import BlastBlock
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

    def persist_contour(self, domain_id: int, expected_version: int, event: BlastEvent) -> int:
        with self._session_factory.begin() as session:
            new_version = guard_domain_versions(session, {domain_id: expected_version})[domain_id]
            SqlAlchemyAssessmentWrites.insert_event_in_session(session, domain_id, event)
            self._fail("after_event_flush")
            return new_version

    def persist_production(
        self, domain_id: int, expected_version: int, event: BlastEvent, actor_id: int | None,
    ) -> int:
        if event.event_type != "production" or event.blast_block_id is not None:
            raise ValueError("Expected an unlinked production Blast Event")
        with self._session_factory.begin() as session:
            guard_domain_versions(session, {domain_id: expected_version})
            block = BlastBlock(
                domain_id=domain_id,
                block_number=event.name.strip(),
                horizon_m=Decimal(str(event.elevation)),
                planned_blast_date=event.event_date,
                status="planned",
                comment=None,
                created_by_user_id=actor_id,
            )
            session.add(block)
            session.flush()
            self._fail("after_block_flush")
            event.blast_block_id = block.id
            SqlAlchemyAssessmentWrites.insert_event_in_session(session, domain_id, event)
            self._fail("after_state_replace")
            self._audit.add_entry(
                session,
                blast_block_id=block.id,
                user_id=actor_id,
                action="create",
                entity_type="blast_block",
                entity_id=block.id,
                description="Создан взрывной блок",
            )
            self._fail("before_commit")
            return block.id

    def _fail(self, stage: str) -> None:
        if self._failure_hook is not None:
            self._failure_hook(stage)
