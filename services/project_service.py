"""User-facing project facade hiding the compatibility Mine/Site pair."""
from __future__ import annotations

from database.models import Mine, Site


class ProjectService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create_project(self, name: str, description: str | None = None) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name is required")
        with self.session_factory.begin() as session:
            mine = Mine(name=clean_name, description=description or None)
            session.add(mine)
            session.flush()
            site = Site(mine_id=mine.id, name=clean_name, description=description or None)
            session.add(site)
            session.flush()
            return site.id
