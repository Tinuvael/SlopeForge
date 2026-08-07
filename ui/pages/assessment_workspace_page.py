"""PostgreSQL-backed host page for one Domain's 2D Assessment workspace."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from database.app_context import AppContext
from repositories.assessment_state_repository import AssessmentStateRepository
from repositories.project_lines_repository import ProjectLinesRepository
from ui.prototype_2d.assessment_workspace import AssessmentWorkspaceWidget


class AssessmentWorkspacePage(QWidget):
    """Own one Domain-scoped assessment state while viewing shared Site lines."""

    def __init__(self, context: AppContext, domain_id: int,
                 domain_name: str | None = None, site_id: int | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self.domain_id = domain_id
        self.domain_name = domain_name
        self.storage_path = context.storage_root / "slopeforge_state.json"
        self.repository = AssessmentStateRepository(context.session_factory)
        self.project_lines_repository = ProjectLinesRepository(context.session_factory)
        loaded = self.repository.load_for_domain(domain_id)
        self.site_id = loaded.site_id if site_id is None else site_id
        self.workspace_id = loaded.workspace_id
        self.state = loaded.state

        def save_callback() -> None:
            if not self.context.current_user.can_edit:
                raise PermissionError("2D Assessment is read-only for the current user")
            saved = self.repository.replace_for_domain(self.domain_id, self.state)
            self.workspace_id = saved.workspace_id

        def persist_dataset_callback(dataset) -> None:
            make_active = dataset.is_active
            self.project_lines_repository.import_dataset(
                self.site_id, dataset, make_active=make_active
            )
            self._reload_site_datasets()

        def set_active_dataset_callback(dataset_id: str) -> None:
            self.project_lines_repository.set_active(self.site_id, dataset_id)
            self._reload_site_datasets()

        self.workspace = AssessmentWorkspaceWidget(
            state=self.state,
            storage_path=self.storage_path,
            save_callback=save_callback,
            parent=self,
            read_only=not self.context.current_user.can_edit,
            persist_dataset_callback=persist_dataset_callback,
            set_active_dataset_callback=set_active_dataset_callback,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.domain_label = QLabel(f"Домен: {domain_name or domain_id}", self)
        layout.addWidget(self.domain_label)
        layout.addWidget(self.workspace)

        # Expose the workspace's bound signals without manufacturing duplicate events.
        self.state_changed = self.workspace.state_changed
        self.state_saved = self.workspace.state_saved

    def open_blast_event(self, event_id: str) -> bool:
        return self.workspace.open_blast_event(event_id)

    def open_assessment_area(self, area_id: str) -> bool:
        return self.workspace.open_assessment_area(area_id)

    def open_dataset(self, dataset_id: str) -> bool:
        return self.workspace.open_dataset(dataset_id)

    def refresh_workspace(self) -> None:
        self.workspace.refresh_workspace()

    def reload_from_repository(self) -> None:
        loaded = self.repository.load_for_domain(self.domain_id)
        previous = {
            "datasets": list(self.state.datasets),
            "blast_events": list(self.state.blast_events),
            "assessment_areas": list(self.state.assessment_areas),
            "technical_cards": list(self.state.technical_cards),
            "evaluations": list(self.state.evaluations),
            "attachments": list(self.state.attachments),
            "workspace_id": self.workspace_id,
        }
        try:
            self.state.datasets[:] = loaded.state.datasets
            self.state.blast_events[:] = loaded.state.blast_events
            self.state.assessment_areas[:] = loaded.state.assessment_areas
            self.state.technical_cards[:] = loaded.state.technical_cards
            self.state.evaluations[:] = loaded.state.evaluations
            self.state.attachments[:] = loaded.state.attachments
            self.workspace_id = loaded.workspace_id
            self.workspace.refresh_workspace()
        except Exception:
            self.state.datasets[:] = previous["datasets"]
            self.state.blast_events[:] = previous["blast_events"]
            self.state.assessment_areas[:] = previous["assessment_areas"]
            self.state.technical_cards[:] = previous["technical_cards"]
            self.state.evaluations[:] = previous["evaluations"]
            self.state.attachments[:] = previous["attachments"]
            self.workspace_id = previous["workspace_id"]
            raise

    def _reload_site_datasets(self) -> None:
        """Refresh shared Site history without touching Domain-owned data."""
        loaded = self.repository.load_for_domain(self.domain_id)
        self.state.datasets[:] = loaded.state.datasets

    def has_active_workflow(self) -> bool:
        return self.workspace.has_active_workflow()

    def cancel_active_workflow(self) -> bool:
        return self.workspace.cancel_active_workflow()

    def save_now(self) -> None:
        self.workspace.save_now()
