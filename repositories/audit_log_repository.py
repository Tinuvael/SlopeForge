from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import AuditLogEntry, User


@dataclass(frozen=True)
class AuditLogEntryRow:
    id: int
    blast_block_id: int
    user_id: int | None
    user_display_name: str
    action: str
    entity_type: str
    entity_id: int | None
    field_name: str | None
    old_value: str | None
    new_value: str | None
    description: str | None
    created_at: datetime


class AuditLogRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def add_entry(
        self,
        session: Session,
        *,
        blast_block_id: int,
        user_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        field_name: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        description: str | None = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            blast_block_id=blast_block_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            description=description,
        )
        session.add(entry)
        session.flush()
        return entry

    def list_for_block(self, blast_block_id: int, limit: int = 200) -> list[AuditLogEntryRow]:
        with self.session_factory() as session:
            entries = list(
                session.scalars(
                    select(AuditLogEntry)
                    .options(joinedload(AuditLogEntry.user))
                    .where(AuditLogEntry.blast_block_id == blast_block_id)
                    .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
                    .limit(limit)
                )
            )
            return [self._to_row(entry) for entry in entries]

    @staticmethod
    def _to_row(entry: AuditLogEntry) -> AuditLogEntryRow:
        user = entry.user
        display_name = "Удалённый пользователь"
        if user is not None:
            display_name = user.full_name or user.username
        return AuditLogEntryRow(
            id=entry.id,
            blast_block_id=entry.blast_block_id,
            user_id=entry.user_id,
            user_display_name=display_name,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            field_name=entry.field_name,
            old_value=entry.old_value,
            new_value=entry.new_value,
            description=entry.description,
            created_at=entry.created_at,
        )
