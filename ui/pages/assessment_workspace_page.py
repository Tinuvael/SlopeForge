"""PostgreSQL-backed host page for a Site's reusable 2D workspace."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from database.app_context import AppContext
from repositories.assessment_state_repository import AssessmentStateRepository
from ui.prototype_2d.assessment_workspace import AssessmentWorkspaceWidget


class AssessmentWorkspacePage(QWidget):
    """Own one Site-scoped assessment state for the page lifetime."""

    def __init__(self, context: AppContext, site_id: int,
                 site_name: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self.site_id = site_id
        self.site_name = site_name
        self.storage_path = context.storage_root / "slopeforge_state.json"
        self.repository = AssessmentStateRepository(context.session_factory)
        loaded = self.repository.load_for_site(site_id)
        self.workspace_id = loaded.workspace_id
        self.state = loaded.state

        def save_callback() -> None:
            saved = self.repository.replace_for_site(self.site_id, self.state)
            self.workspace_id = saved.workspace_id

        self.workspace = AssessmentWorkspaceWidget(
            state=self.state,
            storage_path=self.storage_path,
            save_callback=save_callback,
            parent=self,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.domain_label = QLabel(f"Домен: {site_name or site_id}", self)
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

    def has_active_workflow(self) -> bool:
        return self.workspace.has_active_workflow()

    def cancel_active_workflow(self) -> bool:
        return self.workspace.cancel_active_workflow()

    def save_now(self) -> None:
        self.workspace.save_now()
