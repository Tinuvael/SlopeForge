from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QSizePolicy

from ui.pages.block_card_widgets import CardFrame
from ui.pages.block_overview_widgets import (
    BlockAttachmentPreview,
    BlockGeometryCard,
    BlockRecentActivityCard,
    BlockRelatedEntityList,
)
from ui.pages.entity_overview_widgets import AssessmentMatrixPreview, EngineeringSummaryCard


class AssessmentAttachmentPreview(BlockAttachmentPreview):
    """Assessment attachment preview using the stabilized 6-photo / 7-document sidebar."""


class AssessmentGeometryCard(BlockGeometryCard):
    """Assessment plan card with the same dimensions and resize behaviour as blast pages."""


class AssessmentRecentActivityCard(BlockRecentActivityCard):
    """Assessment activity preview with four stable history slots."""


class AssessmentRelatedEventList(BlockRelatedEntityList):
    """Taller linked-event list; Assessment Overview has no Notes card above the plan."""

    LIST_HEIGHT = 184


class AssessmentCommentsCard(EngineeringSummaryCard):
    """Comments and recommendations share the available card height equally."""

    def __init__(self, title="Comments / recommendations", parent=None):
        super().__init__(title)
        if parent is not None:
            self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.layout.setStretch(self.layout.count() - 1, 1)

    def set_sections(self, sections):
        super().set_sections(sections)
        for index in range(self.sections.count()):
            item = self.sections.itemAt(index)
            widget = item.widget()
            if widget is None or widget.objectName() == "OverviewDivider":
                self.sections.setStretch(index, 0)
                continue
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if widget.layout() is not None:
                widget.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
            self.sections.setStretch(index, 1)


class CompactAssessmentMatrixPreview(AssessmentMatrixPreview):
    """Stored DAI/FCI quadrant sized for the compact Assessment Overview row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(190, 190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(220, 220)


class AssessmentMatrixCard(CardFrame):
    """Compact matrix card; scoring remains entirely outside this presentation widget."""

    def __init__(self, title="Assessment matrix", parent=None):
        super().__init__(title)
        if parent is not None:
            self.setParent(parent)
        self.setMinimumWidth(250)
        self.setMaximumWidth(310)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.preview = CompactAssessmentMatrixPreview()
        self.layout.addWidget(self.preview, 1)
