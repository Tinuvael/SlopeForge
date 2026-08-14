from dataclasses import dataclass

from application.ports.entity_renaming import ProjectRenaming


@dataclass(frozen=True)
class RenameProjectCommand:
    site_id: int
    name: str
    actor_id: int
    can_edit: bool


@dataclass(frozen=True)
class RenameProjectResult:
    site_id: int
    project_name: str


class RenameProject:
    def __init__(self, persistence: ProjectRenaming):
        self._persistence = persistence

    def execute(self, command: RenameProjectCommand) -> RenameProjectResult:
        if not command.can_edit:
            raise PermissionError("Project editing is read-only for the current user")
        name = command.name.strip()
        if not name:
            raise ValueError("Project name is required")
        if len(name) > 255:
            raise ValueError("Project name must be 255 characters or fewer")
        return RenameProjectResult(
            command.site_id, self._persistence.rename_project(command.site_id, name)
        )
