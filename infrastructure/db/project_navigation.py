from application.ports.project_navigation import DomainContext
from repositories.domain_repository import DomainRepository
from repositories.project_lines_repository import ProjectLinesRepository


class SqlAlchemyProjectNavigationQueries:
    def __init__(self, session_factory):
        self._domains = DomainRepository(session_factory)
        self._lines = ProjectLinesRepository(session_factory)

    def get_domain_context(self, domain_id: int) -> DomainContext:
        domain = self._domains.get(domain_id)
        if domain is None:
            raise ValueError(f"Domain {domain_id} does not exist")
        return DomainContext(domain.id, domain.name, domain.site_id, domain.site.name)

    def project_has_active_lines(self, site_id: int) -> bool:
        return self._lines.get_active(site_id) is not None
