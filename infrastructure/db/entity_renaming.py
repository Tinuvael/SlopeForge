"""SQLAlchemy adapters for identity-preserving metadata renames."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from application.errors import DomainNameConflict
from database.models import Domain, Site
from infrastructure.db.domain_version import guard_domain_versions


class SqlAlchemyProjectRenaming:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def rename_project(self, site_id: int, name: str) -> str:
        with self._session_factory.begin() as session:
            site = session.get(Site, site_id)
            if site is None:
                raise ValueError("Project not found")
            site.name = name
            session.flush()
            return site.name


class SqlAlchemyDomainRenaming:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def rename_domain(
        self, domain_id: int, name: str, expected_version: int
    ) -> tuple[int, str, int]:
        try:
            with self._session_factory.begin() as session:
                domain = session.get(Domain, domain_id)
                if domain is None:
                    raise ValueError("Domain not found")
                duplicate = session.scalar(select(Domain.id).where(
                    Domain.site_id == domain.site_id,
                    Domain.name == name,
                    Domain.id != domain_id,
                ))
                if duplicate is not None:
                    raise DomainNameConflict()
                new_version = guard_domain_versions(
                    session, {domain_id: expected_version}
                )[domain_id]
                domain.name = name
                session.flush()
                return domain.site_id, domain.name, new_version
        except IntegrityError as exc:
            # Covers a concurrent insert/rename racing the friendly pre-check.
            raise DomainNameConflict() from exc
