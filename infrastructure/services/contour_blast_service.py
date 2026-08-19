from __future__ import annotations

from sqlalchemy import select

from database.assessment_models import BlastEvent
from infrastructure.db.domain_version import guard_domain_versions
from repositories.audit_log_repository import AuditLogRepository


class ContourBlastService:
    """Focused persistence commands for contour BlastEvent metadata outside the Technical Card."""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.audit_repository = AuditLogRepository(session_factory)

    def update_comment(self, event_id: str, comment: str | None, user, *, domain_id: int,
                       expected_version: int) -> int:
        if not user.can_edit:
            raise PermissionError("Your role is not allowed to edit contour blasts")
        text = str(comment or "")
        with self.session_factory.begin() as session:
            new_version = guard_domain_versions(
                session, {domain_id: expected_version}
            )[domain_id]
            event = session.scalar(select(BlastEvent).where(
                BlastEvent.domain_id == domain_id,
                BlastEvent.logical_id == event_id,
                BlastEvent.event_type == "contour",
            ))
            if event is None:
                raise ValueError("Contour BlastEvent not found")
            old = event.comment or ""
            if old == text:
                return new_version
            event.comment = text or None
            self.audit_repository.add_entry(
                session,
                user_id=user.id,
                action="update",
                entity_type="blast_event",
                entity_id=event.logical_id,
                field_name="comment",
                old_value=old or None,
                new_value=text or None,
                description="Changed field: Comment",
            )
            return new_version
