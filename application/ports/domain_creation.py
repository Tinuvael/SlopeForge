"""Persistence boundary for creating a Site-owned Domain."""
from typing import Protocol


class DomainCreation(Protocol):
    def create_domain(self, site_id: int, name: str, description: str | None = None) -> int: ...
