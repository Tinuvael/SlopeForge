from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.assessment_models import BlastEvent
from database.models import Domain
from infrastructure.db.workflow_status_queries import blast_workflow_states


@dataclass(frozen=True)
class ProductionBlastRow:
    """Block-page read model backed by exactly one production BlastEvent."""
    id: str
    block_number: str
    domain_id: int
    domain_name: str
    site_id: int
    site_name: str
    horizon_m: Decimal
    planned_blast_date: date | None
    status: str
    author_name: str | None
    created_at: datetime
    updated_at: datetime
    comment: str | None
    created_by_user_id: int | None
    is_archived: bool
    archived_at: datetime | None
    domain_version: int


class ProductionBlastRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def list_blocks(self, number_query=None, domain_id=None, site_id=None, status=None,
                    show_archived=False, **_ignored):
        with self.session_factory() as session:
            stmt = (select(BlastEvent)
                    .where(BlastEvent.event_type == "production")
                    .options(joinedload(BlastEvent.domain).joinedload(Domain.site),
                             joinedload(BlastEvent.created_by_user))
                    .order_by(BlastEvent.created_at.desc(), BlastEvent.id.desc()))
            if number_query:
                stmt = stmt.where(BlastEvent.name.ilike(f"%{number_query.strip()}%"))
            if domain_id is not None:
                stmt = stmt.where(BlastEvent.domain_id == domain_id)
            if site_id is not None:
                stmt = stmt.join(BlastEvent.domain).where(Domain.site_id == site_id)
            if not show_archived:
                stmt = stmt.where(BlastEvent.is_archived.is_(False))
            events = list(session.scalars(stmt).unique())
            states = blast_workflow_states(session, events)
            rows = [self._to_row(event, states) for event in events]
            return [row for row in rows if status is None or row.status == status]

    def get_block(self, event_id: str):
        with self.session_factory() as session:
            event = session.scalar(
                select(BlastEvent)
                .where(BlastEvent.logical_id == event_id,
                       BlastEvent.event_type == "production")
                .options(joinedload(BlastEvent.domain).joinedload(Domain.site),
                         joinedload(BlastEvent.created_by_user))
            )
            if event is None:
                return None
            return self._to_row(event, blast_workflow_states(session, [event]))

    @staticmethod
    def _to_row(event: BlastEvent, states) -> ProductionBlastRow:
        site = event.domain.site
        author = ((event.created_by_user.full_name or event.created_by_user.username)
                  if event.created_by_user else None)
        return ProductionBlastRow(
            id=event.logical_id,
            block_number=event.name,
            domain_id=event.domain_id,
            domain_name=event.domain.name,
            site_id=site.id,
            site_name=site.name,
            horizon_m=event.elevation_m,
            planned_blast_date=event.event_date,
            status=str(states[event.logical_id] if event.logical_id in states else states[event.id]),
            author_name=author,
            created_at=event.created_at,
            updated_at=event.updated_at,
            comment=event.comment,
            created_by_user_id=event.created_by_user_id,
            is_archived=event.is_archived,
            archived_at=event.archived_at,
            domain_version=event.domain.version,
        )
