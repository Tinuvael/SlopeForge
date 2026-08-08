from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from database.models import BlastBlock, Domain, Site

@dataclass(frozen=True)
class BlastBlockRow:
    id: int; block_number: str; domain_id: int; domain_name: str; site_id: int; site_name: str; mine_id: int; mine_name: str
    horizon_m: Decimal | None; planned_blast_date: date | None; status: str; author_name: str | None; created_at: datetime; updated_at: datetime; comment: str | None; created_by_user_id: int | None; is_archived: bool; archived_at: datetime | None

class BlastBlockRepository:
    def __init__(self, session_factory: Callable[[], Session]): self.session_factory = session_factory
    def list_blocks(self, number_query=None, domain_id=None, site_id=None, status=None, show_archived=False, **_ignored):
        with self.session_factory() as session:
            stmt = select(BlastBlock).options(joinedload(BlastBlock.domain).joinedload(Domain.site).joinedload(Site.mine), joinedload(BlastBlock.created_by_user)).order_by(BlastBlock.created_at.desc(), BlastBlock.id.desc())
            if number_query: stmt = stmt.where(BlastBlock.block_number.ilike(f"%{number_query.strip()}%"))
            if domain_id is not None: stmt = stmt.where(BlastBlock.domain_id == domain_id)
            if site_id is not None: stmt = stmt.join(BlastBlock.domain).where(Domain.site_id == site_id)
            if status: stmt = stmt.where(BlastBlock.status == status)
            if not show_archived: stmt = stmt.where(BlastBlock.is_archived.is_(False))
            return [self._to_row(x) for x in session.scalars(stmt)]
    def get_block(self, block_id):
        with self.session_factory() as session:
            row = session.scalar(select(BlastBlock).options(joinedload(BlastBlock.domain).joinedload(Domain.site).joinedload(Site.mine), joinedload(BlastBlock.created_by_user)).where(BlastBlock.id == block_id))
            return self._to_row(row) if row else None
    def create_block(self, **values):
        with self.session_factory.begin() as session:
            row = BlastBlock(**values); row.block_number = row.block_number.strip(); session.add(row); session.flush(); session.refresh(row); session.expunge(row); return row
    def update_block(self, block_id, **values):
        with self.session_factory.begin() as session:
            row = session.get(BlastBlock, block_id)
            if row is None: raise ValueError("Blast block not found")
            for key, value in values.items(): setattr(row, key, value.strip() if key == "block_number" else value)
            session.flush(); session.refresh(row); session.expunge(row); return row
    @staticmethod
    def _to_row(block):
        site = block.domain.site; author = (block.created_by_user.full_name or block.created_by_user.username) if block.created_by_user else None
        return BlastBlockRow(block.id, block.block_number, block.domain_id, block.domain.name, site.id, site.name, site.mine_id, site.mine.name, block.horizon_m, block.planned_blast_date, block.status, author, block.created_at, block.updated_at, block.comment, block.created_by_user_id, block.is_archived, block.archived_at)
