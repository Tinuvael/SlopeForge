from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

from ui.pages.block_overview_widgets import (
    BlockAttachmentPreview,
    BlockGeometryCard,
    BlockNotesCard,
    BlockRecentActivityCard,
    BlockRelatedEntityList,
)
from ui.pages.entity_overview_widgets import EngineeringSummaryCard


class ContourAttachmentPreview(BlockAttachmentPreview):
    """Contour attachment preview with the stabilized Block sidebar behaviour."""


class ContourGeometryCard(BlockGeometryCard):
    """Contour plan card using the same stable dimensions as Production Block."""


class ContourNotesCard(BlockNotesCard):
    """Contour Notes card using the same compact scrollable editor viewport."""


class ContourRecentActivityCard(BlockRecentActivityCard):
    """Contour activity preview with four fixed-height history slots."""


class ContourRelatedEntityList(BlockRelatedEntityList):
    """Contour related Assessment Areas with the same row geometry and styling."""


class ContourEngineeringNotesCard(EngineeringSummaryCard):
    """Contour engineering notes split available height equally between design and fact."""

    def __init__(self, title="Engineering notes", parent=None):
        super().__init__(title)
        if parent is not None:
            self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # CardFrame adds the title first and EngineeringSummaryCard adds the
        # sections layout second. Let the sections consume the remaining card
        # height when the neighbouring Recent activity card is taller.
        self.layout.setStretch(self.layout.count() - 1, 1)

    def set_sections(self, sections):
        super().set_sections(sections)
        # EngineeringSummaryCard alternates section widgets and fixed dividers.
        # Give every real section the same stretch so Blast design and
        # Execution fact always receive equal vertical space.
        for index in range(self.sections.count()):
            item = self.sections.itemAt(index)
            widget = item.widget()
            if widget is None or widget.objectName() == "OverviewDivider":
                self.sections.setStretch(index, 0)
                continue
            widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            if widget.layout() is not None:
                widget.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
            self.sections.setStretch(index, 1)
