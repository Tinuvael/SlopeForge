from dataclasses import dataclass

from application.ports.project_creation import ProjectCreation, ProjectLinesCreationSupport


@dataclass(frozen=True)
class CreateProjectCommand:
    name: str
    description: str | None
    optional_project_lines_path: str | None
    actor_id: int
    can_edit: bool


@dataclass(frozen=True)
class CreateProjectResult:
    site_id: int
    project_name: str
    project_created: bool
    project_lines_requested: bool
    project_lines_saved: bool
    project_lines_warning: str | None = None


class CreateProject:
    def __init__(self, persistence: ProjectCreation, lines: ProjectLinesCreationSupport):
        self._persistence, self._lines = persistence, lines

    def execute(self, command: CreateProjectCommand) -> CreateProjectResult:
        if not command.can_edit:
            raise PermissionError("Project creation is read-only for the current user")
        path = (command.optional_project_lines_path or "").strip()
        dataset = self._lines.prepare(path) if path else None
        site_id = self._persistence.create_project(command.name, command.description)
        warning = None
        saved = False
        if dataset is not None:
            try:
                self._lines.save_active(site_id, dataset)
                saved = True
            except Exception as exc:
                warning = str(exc)
        return CreateProjectResult(site_id, command.name.strip(), True, bool(path), saved, warning)
