from dataclasses import dataclass

from application.ports.entity_renaming import DomainRenaming


@dataclass(frozen=True)
class RenameDomainCommand:
    domain_id: int
    name: str
    expected_version: int
    actor_id: int
    can_edit: bool


@dataclass(frozen=True)
class RenameDomainResult:
    domain_id: int
    site_id: int
    domain_name: str
    new_version: int


class RenameDomain:
    def __init__(self, persistence: DomainRenaming):
        self._persistence = persistence

    def execute(self, command: RenameDomainCommand) -> RenameDomainResult:
        if not command.can_edit:
            raise PermissionError("Domain editing is read-only for the current user")
        name = command.name.strip()
        if not name:
            raise ValueError("Domain name is required")
        if len(name) > 255:
            raise ValueError("Domain name must be 255 characters or fewer")
        site_id, stored_name, new_version = self._persistence.rename_domain(
            command.domain_id, name, command.expected_version
        )
        return RenameDomainResult(
            command.domain_id, site_id, stored_name, new_version
        )
