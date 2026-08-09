
from app.localization import tr
"""Compatibility window around the embeddable assessment workspace."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QMainWindow, QMessageBox

from app.qt import apply_window_icon
from prototype_2d.blast_event_storage import load_blast_event_state, save_blast_event_state
from ui.widgets.assessment_workspace import (
    ASSESSMENT_HANDLE_ROLE,
    ASSESSMENT_SELECTION_ROLE,
    BLAST_CONTEXT_ROLE,
    BLAST_GEOMETRY_ROLE,
    PROJECT_LINE_ROLE,
    AssessmentCandidateDialog,
    AssessmentEventLinksDialog,
    AssessmentWorkspaceWidget,
    BlastEventDialog,
    BlastEventPlanView,
    DatasetHistoryDialog,
    ManualAssessmentEventLinkDialog,
    PolygonVertexHandle,
)

# Responsive ``QScrollArea`` detail labels now live in AssessmentWorkspaceWidget
# and retain ``setWordWrap(True)``, ``setToolTip(value)`` and
# ``ScrollBarAlwaysOff`` behaviour.


class BlastEventWindow(QMainWindow):
    """Own JSON persistence and host the reusable workspace widget."""

    closed = Signal()

    def __init__(self, parent=None, storage_path: str | Path | None = None):
        super().__init__(parent, Qt.WindowType.Window)
        self.storage_path = storage_path
        self.state = load_blast_event_state(storage_path)

        def save_callback():
            save_blast_event_state(self.state, self.storage_path)

        self.workspace = AssessmentWorkspaceWidget(
            self.state, self.storage_path, save_callback, self
        )
        self.setCentralWidget(self.workspace)
        self.setWindowTitle(tr("SlopeForge — 2D Assessment Workspace"))
        self.resize(1300, 800)
        self.setMinimumSize(1000, 650)
        apply_window_icon(self)

    def __getattr__(self, name):
        """Keep access to former workspace attributes during the transition."""
        workspace = self.__dict__.get("workspace")
        if workspace is not None and hasattr(workspace, name):
            return getattr(workspace, name)
        raise AttributeError(name)

    def open_blast_event(self, event_id: str) -> bool:
        return self.workspace.open_blast_event(event_id)

    def open_assessment_area(self, area_id: str) -> bool:
        return self.workspace.open_assessment_area(area_id)

    def open_dataset(self, dataset_id: str) -> bool:
        return self.workspace.open_dataset(dataset_id)

    def refresh_workspace(self) -> None:
        self.workspace.refresh_workspace()

    def closeEvent(self, event):
        if self.workspace.has_active_workflow():
            answer = QMessageBox.warning(
                self,
                "Несохранённая геометрия",
                "Имеются несохранённые изменения геометрии.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
            self.workspace.cancel_active_workflow()
        try:
            self.workspace.save_now()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить данные. Окно останется открытым.\n\n{exc}",
            )
            event.ignore()
            return
        self.closed.emit()
        super().closeEvent(event)
