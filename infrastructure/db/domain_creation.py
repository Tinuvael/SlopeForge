from repositories.domain_repository import DomainRepository


class SqlAlchemyDomainCreation:
    def __init__(self, session_factory): self._repository = DomainRepository(session_factory)

    def create_domain(self, site_id: int, name: str, description: str | None = None) -> int:
        # DomainRepository historically strips but permits an empty name; Phase 4C preserves it.
        return self._repository.create(site_id, name, description).id
