"""Authenticated user data shared across application boundaries."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    full_name: str | None
    role: str

    @property
    def display_name(self) -> str:
        return self.full_name or self.username

    @property
    def can_edit(self) -> bool:
        return self.role in {"admin", "editor"}
