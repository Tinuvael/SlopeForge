"""Application command for archiving or restoring one production Block."""
from dataclasses import dataclass

from application.ports.blast_block_archive import BlastBlockArchivePersistence


@dataclass(frozen=True)
class SetBlastBlockArchivedCommand:
    block_id: int
    archived: bool
    actor_id: int
    can_edit: bool
    expected_version: int | None = None


class SetBlastBlockArchived:
    def __init__(self, persistence: BlastBlockArchivePersistence):
        self._persistence = persistence

    def execute(self, command: SetBlastBlockArchivedCommand) -> None:
        if not command.can_edit:
            raise PermissionError("Your role is not allowed to archive or restore blocks")
        expected = (command.expected_version if command.expected_version is not None
                    else self._persistence.load_domain_version(command.block_id))
        self._persistence.set_archived(
            command.block_id, expected, command.archived, command.actor_id)
