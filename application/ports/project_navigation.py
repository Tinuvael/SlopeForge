from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DomainContext:
    domain_id: int
    domain_name: str
    site_id: int
    site_name: str


class ProjectNavigationQueries(Protocol):
    def get_domain_context(self, domain_id: int) -> DomainContext: ...
    def project_has_active_lines(self, site_id: int) -> bool: ...
