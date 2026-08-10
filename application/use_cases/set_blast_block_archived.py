"""Application command for archiving or restoring one production Block."""
from dataclasses import dataclass

from application.ports.blast_block_archive import BlastBlockArchivePersistence


@dataclass(frozen=True)
class SetBlastBlockArchivedCommand:
    block_id: int
    archived: bool
    actor_id: int
    can_edit: bool


class SetBlastBlockArchived:
    def __init__(self, persistence: BlastBlockArchivePersistence):
        self._persistence = persistence

    def execute(self, command: SetBlastBlockArchivedCommand) -> None:
        if not command.can_edit:
            raise PermissionError("Your role is not allowed to archive or restore blocks")
        self._persistence.set_archived(command.block_id, command.archived, command.actor_id)
