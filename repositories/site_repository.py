from __future__ import annotations

from collections.abc import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Site


class SiteRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def list_sites(self) -> list[Site]:
        with self.session_factory() as session:
            items = list(session.scalars(select(Site).order_by(Site.name, Site.id)))
            for item in items:
                session.expunge(item)
            return items

    def create_site(self, name: str, description: str | None = None) -> Site:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name is required")
        with self.session_factory.begin() as session:
            site = Site(name=clean_name, description=description or None)
            session.add(site); session.flush(); session.refresh(site); session.expunge(site)
            return site

    def update_site(self, site_id: int, name: str, description: str | None = None) -> Site:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name is required")
        with self.session_factory.begin() as session:
            site = session.get(Site, site_id)
            if site is None:
                raise ValueError("Project not found")
            site.name = clean_name
            site.description = description or None
            session.flush(); session.refresh(site); session.expunge(site)
            return site
