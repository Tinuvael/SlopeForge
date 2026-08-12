"""Shared result contract for version-guarded Domain writes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DomainWriteResult:
    new_version: int
    workspace_id: int | None = None
