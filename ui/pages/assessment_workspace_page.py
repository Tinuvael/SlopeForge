"""Embedded host page for the reusable 2D assessment workspace."""
from pathlib import Path

from PySide6.QtWidgets import QVBoxLayout, QWidget

from prototype_2d.blast_event_storage import (
    default_blast_event_storage_path,
    load_blast_event_state,
    save_blast_event_state,
)
from ui.prototype_2d.assessment_workspace import AssessmentWorkspaceWidget


class AssessmentWorkspacePage(QWidget):
    """Own one assessment state and its JSON persistence for the page lifetime."""

    def __init__(self, storage_path: str | Path | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.storage_path = (
            Path(storage_path)
            if storage_path is not None
            else default_blast_event_storage_path()
        )
        self.state = load_blast_event_state(self.storage_path)

        def save_callback() -> None:
            save_blast_event_state(self.state, self.storage_path)

        self.workspace = AssessmentWorkspaceWidget(
            state=self.state,
            storage_path=self.storage_path,
            save_callback=save_callback,
            parent=self,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
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
