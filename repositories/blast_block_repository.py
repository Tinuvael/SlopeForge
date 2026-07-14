from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import BlastBlock, Site, User


@dataclass(frozen=True)
class BlastBlockRow:
    id: int
    block_number: str
    mine_id: int
    mine_name: str
    site_id: int
    site_name: str
    horizon_m: Decimal | None
    planned_blast_date: date | None
    status: str
    author_name: str | None
    created_at: datetime
    updated_at: datetime
    comment: str | None
    created_by_user_id: int | None


class BlastBlockRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def list_blocks(self, number_query: str | None = None, mine_id: int | None = None, site_id: int | None = None, status: str | None = None) -> list[BlastBlockRow]:
        with self.session_factory() as session:
            stmt = (
                select(BlastBlock)
                .options(
                    joinedload(BlastBlock.site).joinedload(Site.mine),
                    joinedload(BlastBlock.created_by_user),
                )
                .order_by(BlastBlock.created_at.desc(), BlastBlock.id.desc())
            )
            if number_query:
                stmt = stmt.where(BlastBlock.block_number.ilike(f"%{number_query.strip()}%"))
            if mine_id is not None:
                stmt = stmt.join(BlastBlock.site).where(Site.mine_id == mine_id)
            if site_id is not None:
                stmt = stmt.where(BlastBlock.site_id == site_id)
            if status:
                stmt = stmt.where(BlastBlock.status == status)
            blocks = list(session.scalars(stmt))
            return [self._to_row(block) for block in blocks]

    def get_block(self, block_id: int) -> BlastBlockRow | None:
        with self.session_factory() as session:
            block = session.scalar(
                select(BlastBlock)
                .options(joinedload(BlastBlock.site).joinedload(Site.mine), joinedload(BlastBlock.created_by_user))
                .where(BlastBlock.id == block_id)
            )
            return self._to_row(block) if block else None

    def create_block(self, *, site_id: int, block_number: str, horizon_m: Decimal | None, planned_blast_date: date | None, status: str, comment: str | None, created_by_user_id: int) -> BlastBlock:
        with self.session_factory() as session:
            try:
                block = BlastBlock(
                    site_id=site_id,
                    block_number=block_number.strip(),
                    horizon_m=horizon_m,
                    planned_blast_date=planned_blast_date,
                    status=status,
                    comment=comment or None,
                    created_by_user_id=created_by_user_id,
                )
                session.add(block)
                session.commit()
                session.refresh(block)
                session.expunge(block)
                return block
            except Exception:
                session.rollback()
                raise

    def update_block(self, *, block_id: int, site_id: int, block_number: str, horizon_m: Decimal | None, planned_blast_date: date | None, status: str, comment: str | None) -> BlastBlock:
        with self.session_factory() as session:
            try:
                block = session.get(BlastBlock, block_id)
                if block is None:
                    raise ValueError("Взрывной блок не найден")
                block.site_id = site_id
                block.block_number = block_number.strip()
                block.horizon_m = horizon_m
                block.planned_blast_date = planned_blast_date
                block.status = status
                block.comment = comment or None
                session.commit()
                session.refresh(block)
                session.expunge(block)
                return block
            except Exception:
                session.rollback()
                raise

    @staticmethod
    def _to_row(block: BlastBlock) -> BlastBlockRow:
        author = block.created_by_user.full_name or block.created_by_user.username if block.created_by_user else None
        return BlastBlockRow(
            id=block.id,
            block_number=block.block_number,
            mine_id=block.site.mine_id,
            mine_name=block.site.mine.name,
            site_id=block.site_id,
            site_name=block.site.name,
            horizon_m=block.horizon_m,
            planned_blast_date=block.planned_blast_date,
            status=block.status,
            author_name=author,
            created_at=block.created_at,
            updated_at=block.updated_at,
            comment=block.comment,
            created_by_user_id=block.created_by_user_id,
        )
