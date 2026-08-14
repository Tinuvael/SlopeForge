"""Persistence boundaries for focused Project and Domain renames."""
from typing import Protocol


class ProjectRenaming(Protocol):
    def rename_project(self, site_id: int, name: str) -> str: ...


class DomainRenaming(Protocol):
    def rename_domain(
        self, domain_id: int, name: str, expected_version: int
    ) -> tuple[int, str, int]: ...
