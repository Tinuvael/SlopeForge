from __future__ import annotations

from collections.abc import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import Mine, Site


class SiteRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def list_sites(self, mine_id: int | None = None) -> list[Site]:
        with self.session_factory() as session:
            stmt = select(Site).options(joinedload(Site.mine)).order_by(Site.name)
            if mine_id is not None:
                stmt = stmt.where(Site.mine_id == mine_id)
            items = list(session.scalars(stmt))
            for item in items:
                session.expunge(item)
            return items

    def create_site(self, mine_id: int, name: str, description: str | None) -> Site:
        with self.session_factory() as session:
            try:
                if session.get(Mine, mine_id) is None:
                    raise ValueError("Selected mine not found")
                site = Site(mine_id=mine_id, name=name.strip(), description=description or None)
                session.add(site)
                session.commit()
                session.refresh(site)
                session.expunge(site)
                return site
            except Exception:
                session.rollback()
                raise

    def update_site(self, site_id: int, mine_id: int, name: str, description: str | None) -> Site:
        with self.session_factory() as session:
            try:
                site = session.get(Site, site_id)
                if site is None:
                    raise ValueError("Site not found")
                if session.get(Mine, mine_id) is None:
                    raise ValueError("Selected mine not found")
                site.mine_id = mine_id
                site.name = name.strip()
                site.description = description or None
                session.commit()
                session.refresh(site)
                session.expunge(site)
                return site
            except Exception:
                session.rollback()
                raise
