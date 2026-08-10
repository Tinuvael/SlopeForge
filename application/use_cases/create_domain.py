from dataclasses import dataclass

from application.ports.domain_creation import DomainCreation


@dataclass(frozen=True)
class CreateDomainCommand:
    site_id: int
    name: str
    description: str | None
    actor_id: int
    can_edit: bool


@dataclass(frozen=True)
class CreateDomainResult:
    domain_id: int
    site_id: int
    domain_name: str


class CreateDomain:
    def __init__(self, persistence: DomainCreation): self._persistence = persistence

    def execute(self, command: CreateDomainCommand) -> CreateDomainResult:
        if not command.can_edit:
            raise PermissionError("Domain creation is read-only for the current user")
        domain_id = self._persistence.create_domain(command.site_id, command.name, command.description)
        return CreateDomainResult(domain_id, command.site_id, command.name.strip())
