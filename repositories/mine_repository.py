from __future__ import annotations

from collections.abc import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Mine


class MineRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def list_mines(self) -> list[Mine]:
        with self.session_factory() as session:
            items = list(session.scalars(select(Mine).order_by(Mine.name)))
            for item in items:
                session.expunge(item)
            return items

    def create_mine(self, name: str, description: str | None) -> Mine:
        with self.session_factory() as session:
            try:
                mine = Mine(name=name.strip(), description=description or None)
                session.add(mine)
                session.commit()
                session.refresh(mine)
                session.expunge(mine)
                return mine
            except Exception:
                session.rollback()
                raise

    def update_mine(self, mine_id: int, name: str, description: str | None) -> Mine:
        with self.session_factory() as session:
            try:
                mine = session.get(Mine, mine_id)
                if mine is None:
                    raise ValueError("Mine not found")
                mine.name = name.strip()
                mine.description = description or None
                session.commit()
                session.refresh(mine)
                session.expunge(mine)
                return mine
            except Exception:
                session.rollback()
                raise
