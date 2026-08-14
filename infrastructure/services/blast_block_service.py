from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from application.dto.current_user import CurrentUser
from database.models import BlastBlock, Domain
from database.assessment_models import BlastEvent
from infrastructure.db.assessment_writes import SqlAlchemyAssessmentWrites
from repositories.audit_log_repository import AuditLogRepository
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.domain_repository import DomainRepository
from infrastructure.db.domain_version import guard_domain_versions

AUDIT_FIELD_LABELS = {"block_number": "Номер блока", "domain_id": "Домен", "horizon_m": "Горизонт", "comment": "Комментарий"}
AUDITED_FIELDS = tuple(AUDIT_FIELD_LABELS)

class PermissionDenied(ValueError): pass
class ValidationError(ValueError): pass

@dataclass(frozen=True)
class BlastBlockInput:
    domain_id: int | None
    block_number: str
    horizon_text: str
    comment: str | None

class BlastBlockService:
    def __init__(self, block_repository: BlastBlockRepository, domain_repository: DomainRepository, audit_repository: AuditLogRepository | None = None):
        self.block_repository = block_repository
        self.domain_repository = domain_repository
        self.session_factory = getattr(block_repository, "session_factory", None)
        self.audit_repository = audit_repository or (AuditLogRepository(self.session_factory) if self.session_factory else None)

    def list_blocks(self, **filters): return self.block_repository.list_blocks(**filters)
    def get_block(self, block_id): return self.block_repository.get_block(block_id)
    def is_linked_to_production_event(self, block_id: int) -> bool:
        if self.session_factory is None: return False
        from database.assessment_models import BlastEvent
        with self.session_factory() as session:
            return session.scalar(select(BlastEvent.id).where(BlastEvent.blast_block_id==block_id,BlastEvent.event_type=="production")) is not None

    def active_geometry_elevation(self, block_id: int):
        from database.assessment_models import BlastEventGeometryRevision
        with self.session_factory() as session:
            return session.scalar(select(BlastEventGeometryRevision.elevation_m).join(BlastEvent).where(
                BlastEvent.blast_block_id==block_id,
                BlastEventGeometryRevision.is_active.is_(True)))

    def set_archived(self, block_id: int, archived: bool, user: CurrentUser) -> None:
        self._check_can_edit(user)
        with self.session_factory.begin() as session:
            block = session.get(BlastBlock, block_id)
            if block is None: raise ValidationError("Blast block not found")
            block.is_archived = archived
            block.archived_at = datetime.now(timezone.utc) if archived else None

    def create_block(self, data: BlastBlockInput, user: CurrentUser) -> int:
        self._check_can_edit(user); horizon = self._validate(data)
        if self.session_factory is None:
            return self.block_repository.create_block(domain_id=data.domain_id, block_number=data.block_number, horizon_m=horizon, comment=data.comment, created_by_user_id=user.id).id
        try:
            with self.session_factory.begin() as session:
                block = BlastBlock(domain_id=data.domain_id, block_number=data.block_number.strip(), horizon_m=horizon, comment=data.comment or None, created_by_user_id=user.id)
                session.add(block); session.flush()
                self.audit_repository.add_entry(session, blast_block_id=block.id, user_id=user.id, action="create", entity_type="blast_block", entity_id=block.id, description="Создан взрывной блок")
                return block.id
        except SQLAlchemyError as exc: raise ValidationError("Could not save the block in PostgreSQL. Check the data and database migrations.") from exc

    def update_block(self, block_id: int, data: BlastBlockInput, user: CurrentUser,
                     *, expected_version: int, target_expected_version: int | None = None) -> int:
        self._check_can_edit(user); horizon = self._validate(data)
        if self.session_factory is None:
            self.block_repository.update_block(block_id=block_id,domain_id=data.domain_id,block_number=data.block_number,horizon_m=horizon,comment=data.comment)
            return block_id
        try:
            with self.session_factory.begin() as session:
                block = session.get(BlastBlock, block_id)
                if block is None: raise ValueError("Blast block not found")
                old_domain = session.get(Domain, block.domain_id); new_domain = session.get(Domain, data.domain_id)
                if new_domain is None: raise ValidationError("Select an existing Domain")
                if old_domain.site_id != new_domain.site_id: raise ValidationError("A block can only move between Domains of the same project")
                expected = {block.domain_id: expected_version}
                if data.domain_id != block.domain_id:
                    if target_expected_version is None: raise ValidationError("Moving a Block between Domains requires the target Domain version")
                    expected[data.domain_id] = target_expected_version
                guard_domain_versions(session, expected)
                new_values = {"block_number": data.block_number.strip(), "domain_id": data.domain_id, "horizon_m": horizon, "comment": data.comment or None}
                old_values = {field: getattr(block, field) for field in AUDITED_FIELDS}
                names = {d.id: d.name for d in session.query(Domain).filter(Domain.id.in_({block.domain_id, data.domain_id})).all()}
                for field, old_text, new_text in build_audit_changes(old_values, new_values, names):
                    self.audit_repository.add_entry(session, blast_block_id=block.id, user_id=user.id, action="update", entity_type="blast_block", entity_id=block.id, field_name=field, old_value=old_text, new_value=new_text, description=f"Изменено поле: {AUDIT_FIELD_LABELS[field]}")
                source_domain_id = block.domain_id
                event = session.scalar(select(BlastEvent).where(
                    BlastEvent.blast_block_id == block.id,
                    BlastEvent.event_type == "production"))
                if event is None: raise ValidationError("Linked production BlastEvent was not found")
                for field, value in new_values.items(): setattr(block, field, value)
                event.name, event.elevation_m, event.domain_id = (
                    block.block_number, block.horizon_m, block.domain_id)
                session.flush()
                if source_domain_id != block.domain_id:
                    helper = SqlAlchemyAssessmentWrites(self.session_factory)
                    helper._remove_current_cross_domain_links(session, source_domain_id)
                    helper._remove_current_cross_domain_links(session, block.domain_id)
                    helper._rebuild_current_suggestions(session, block.domain_id)
                return block_id
        except SQLAlchemyError as exc: raise ValidationError("Could not update the block in PostgreSQL. Check the data and database migrations.") from exc

    def update_metadata(self, block_id, *, domain_id, block_number, horizon_text,
                        user, expected_version, target_expected_version=None):
        """Focused existing-Block command; comments are intentionally untouched."""
        current = self.get_block(block_id)
        if current is None: raise ValidationError("Blast block not found")
        return self.update_block(block_id, BlastBlockInput(domain_id, block_number,
            horizon_text, current.comment), user, expected_version=expected_version,
            target_expected_version=target_expected_version)

    def update_comment(self, block_id, comment, user, *, expected_version):
        current = self.get_block(block_id)
        if current is None: raise ValidationError("Blast block not found")
        return self.update_block(block_id, BlastBlockInput(current.domain_id,
            current.block_number, "" if current.horizon_m is None else str(current.horizon_m),
            comment), user, expected_version=expected_version)

    def _check_can_edit(self, user):
        if not user.can_edit: raise PermissionDenied("Your role is not allowed to create or edit blocks")
    def _validate(self, data):
        if not data.block_number.strip(): raise ValidationError("Block number is required")
        if data.domain_id is None or self.domain_repository.get(data.domain_id) is None: raise ValidationError("Select an existing Domain")
        if not data.horizon_text.strip(): return None
        try: return Decimal(data.horizon_text.replace(",", "."))
        except InvalidOperation as exc: raise ValidationError("Horizon must be a number") from exc

def build_audit_changes(old_values, new_values, domain_names=None):
    return [(field, format_audit_value(field, old_values.get(field), domain_names), format_audit_value(field, new_values.get(field), domain_names)) for field in AUDITED_FIELDS if old_values.get(field) != new_values.get(field)]

def format_audit_value(field_name, value, domain_names=None):
    if value is None: return None
    if field_name == "horizon_m" and isinstance(value, Decimal):
        text = format(value.normalize(), "f"); return text.rstrip("0").rstrip(".") if "." in text else text
    if field_name == "domain_id": return (domain_names or {}).get(int(value), str(value))
    return str(value)
