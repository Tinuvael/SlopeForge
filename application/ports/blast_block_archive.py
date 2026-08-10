"""Focused persistence boundary for BlastBlock archive state."""
from typing import Protocol


class BlastBlockArchivePersistence(Protocol):
    def set_archived(self, block_id: int, archived: bool, actor_id: int) -> None: ...
