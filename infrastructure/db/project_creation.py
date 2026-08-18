"""SQLAlchemy adapter for creating one Project/Site."""
from database.models import Site


class SqlAlchemyProjectCreation:
    def __init__(self, session_factory): self._session_factory = session_factory

    def create_project(self, name: str, description: str | None = None) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name is required")
        with self._session_factory.begin() as session:
            site = Site(name=clean_name, description=description or None)
            session.add(site); session.flush()
            return site.id
