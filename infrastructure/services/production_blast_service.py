from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from application.dto.current_user import CurrentUser
from database.assessment_models import BlastEvent, BlastEventGeometryRevision
from database.models import Domain
from infrastructure.db.assessment_writes import SqlAlchemyAssessmentWrites
from infrastructure.db.domain_version import guard_domain_versions
from repositories.audit_log_repository import AuditLogRepository
from repositories.domain_repository import DomainRepository
from repositories.production_blast_repository import ProductionBlastRepository

AUDIT_FIELD_LABELS = {
    "name": "Block number",
    "domain_id": "Domain",
    "elevation_m": "Horizon",
    "comment": "Comment",
}
AUDITED_FIELDS = tuple(AUDIT_FIELD_LABELS)


class PermissionDenied(ValueError):
    pass


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ProductionBlastInput:
    domain_id: int | None
    block_number: str
    horizon_text: str
    comment: str | None


class ProductionBlastService:
    """Block-page commands over a single production BlastEvent row."""
    def __init__(self, repository: ProductionBlastRepository,
                 domain_repository: DomainRepository,
                 audit_repository: AuditLogRepository | None = None):
        self.repository = repository
        self.domain_repository = domain_repository
        self.session_factory = repository.session_factory
        self.audit_repository = audit_repository or AuditLogRepository(self.session_factory)

    def list_blocks(self, **filters):
        return self.repository.list_blocks(**filters)

    def get_block(self, event_id):
        return self.repository.get_block(event_id)

    def active_geometry_elevation(self, event_id: str):
        with self.session_factory() as session:
            return session.scalar(
                select(BlastEventGeometryRevision.elevation_m)
                .join(BlastEvent)
                .where(BlastEvent.logical_id == event_id,
                       BlastEvent.event_type == "production",
                       BlastEventGeometryRevision.is_active.is_(True))
            )

    def set_archived(self, event_id: str, archived: bool, user: CurrentUser,
                     *, expected_version: int) -> int:
        self._check_can_edit(user)
        from datetime import datetime, timezone
        with self.session_factory.begin() as session:
            event = self._event(session, event_id)
            new_version = guard_domain_versions(
                session, {event.domain_id: expected_version})[event.domain_id]
            if event.is_archived == archived:
                return new_version
            old_value = "archived" if event.is_archived else "active"
            new_value = "archived" if archived else "active"
            event.is_archived = archived
            event.archived_at = datetime.now(timezone.utc) if archived else None
            if not archived:
                event.archive_reason = None
            self.audit_repository.add_entry(
                session,
                user_id=user.id,
                action="update",
                entity_type="blast_event",
                entity_id=event.logical_id,
                field_name="archive_state",
                old_value=old_value,
                new_value=new_value,
                description="Archived production Block" if archived else "Restored production Block",
            )
            return new_version

    def update_metadata(self, event_id, *, domain_id, block_number, horizon_text,
                        user, expected_version, target_expected_version=None):
        current = self.get_block(event_id)
        if current is None:
            raise ValidationError("Production Blast Event not found")
        return self.update_block(
            event_id,
            ProductionBlastInput(domain_id, block_number, horizon_text, current.comment),
            user,
            expected_version=expected_version,
            target_expected_version=target_expected_version,
        )

    def update_comment(self, event_id, comment, user, *, expected_version):
        current = self.get_block(event_id)
        if current is None:
            raise ValidationError("Production Blast Event not found")
        return self.update_block(
            event_id,
            ProductionBlastInput(current.domain_id, current.block_number,
                                 str(current.horizon_m), comment),
            user,
            expected_version=expected_version,
        )

    def update_block(self, event_id: str, data: ProductionBlastInput, user: CurrentUser,
                     *, expected_version: int, target_expected_version: int | None = None) -> str:
        self._check_can_edit(user)
        elevation = self._validate(data)
        try:
            with self.session_factory.begin() as session:
                event = self._event(session, event_id)
                old_domain = session.get(Domain, event.domain_id)
                new_domain = session.get(Domain, data.domain_id)
                if new_domain is None:
                    raise ValidationError("Select an existing Domain")
                if old_domain.site_id != new_domain.site_id:
                    raise ValidationError("A block can only move between Domains of the same project")
                expected = {event.domain_id: expected_version}
                if data.domain_id != event.domain_id:
                    if target_expected_version is None:
                        raise ValidationError("Moving a Block between Domains requires the target Domain version")
                    expected[data.domain_id] = target_expected_version
                guard_domain_versions(session, expected)
                old_values = {field: getattr(event, field) for field in AUDITED_FIELDS}
                new_values = {
                    "name": data.block_number.strip(),
                    "domain_id": data.domain_id,
                    "elevation_m": elevation,
                    "comment": data.comment or None,
                }
                names = {row.id: row.name for row in session.scalars(
                    select(Domain).where(Domain.id.in_({event.domain_id, data.domain_id})))}
                for field, old_text, new_text in build_audit_changes(old_values, new_values, names):
                    self.audit_repository.add_entry(
                        session, user_id=user.id, action="update",
                        entity_type="blast_event", entity_id=event.logical_id,
                        field_name=field, old_value=old_text, new_value=new_text,
                        description=f"Changed field: {AUDIT_FIELD_LABELS[field]}",
                    )
                source_domain_id = event.domain_id
                for field, value in new_values.items():
                    setattr(event, field, value)
                session.flush()
                if source_domain_id != event.domain_id:
                    helper = SqlAlchemyAssessmentWrites(self.session_factory)
                    helper._remove_current_cross_domain_links(session, source_domain_id)
                    helper._remove_current_cross_domain_links(session, event.domain_id)
                    helper._rebuild_current_suggestions(session, event.domain_id)
                return event.logical_id
        except SQLAlchemyError as exc:
            raise ValidationError(
                "Could not update the production Blast Event in PostgreSQL. Check the data and database migrations."
            ) from exc

    def _event(self, session, event_id: str) -> BlastEvent:
        event = session.scalar(select(BlastEvent).where(
            BlastEvent.logical_id == event_id,
            BlastEvent.event_type == "production"))
        if event is None:
            raise ValidationError("Production Blast Event not found")
        return event

    def _check_can_edit(self, user):
        if not user.can_edit:
            raise PermissionDenied("Your role is not allowed to create or edit blocks")

    def _validate(self, data):
        if not data.block_number.strip():
            raise ValidationError("Block number is required")
        if data.domain_id is None or self.domain_repository.get(data.domain_id) is None:
            raise ValidationError("Select an existing Domain")
        if not data.horizon_text.strip():
            raise ValidationError("Horizon is required for a production Blast Event")
        try:
            return Decimal(data.horizon_text.replace(",", "."))
        except InvalidOperation as exc:
            raise ValidationError("Horizon must be a number") from exc


def build_audit_changes(old_values, new_values, domain_names=None):
    return [
        (field,
         format_audit_value(field, old_values.get(field), domain_names),
         format_audit_value(field, new_values.get(field), domain_names))
        for field in AUDITED_FIELDS if old_values.get(field) != new_values.get(field)
    ]


def format_audit_value(field_name, value, domain_names=None):
    if value is None:
        return None
    if field_name == "elevation_m" and isinstance(value, Decimal):
        text = format(value.normalize(), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    if field_name == "domain_id":
        return (domain_names or {}).get(int(value), str(value))
    return str(value)
