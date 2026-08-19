from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.localization import tr
from ui.pages.block_card_widgets import CardFrame
from ui.pages.block_overview_widgets import (
    BlockAttachmentPreview,
    BlockGeometryCard,
    BlockRecentActivityCard,
    BlockRelatedEntityList,
)
from ui.pages.entity_overview_widgets import AssessmentMatrixPreview, EngineeringSummaryCard, OverviewLinkButton


class AssessmentAttachmentPreview(BlockAttachmentPreview):
    """Assessment attachment preview using the stabilized 6-photo / 7-document sidebar."""


class AssessmentGeometryCard(BlockGeometryCard):
    """Assessment plan card with the same dimensions and resize behaviour as blast pages."""


class AssessmentRecentActivityCard(BlockRecentActivityCard):
    """Assessment activity preview with four stable history slots."""


class AssessmentRelatedEventList(BlockRelatedEntityList):
    """Linked-event card that may grow vertically beside the plan and state summaries."""

    LIST_HEIGHT = 184

    def __init__(self, title: str):
        super().__init__(title)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.list.setMinimumHeight(self.LIST_HEIGHT)
        self.list.setMaximumHeight(16777215)
        self.list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.empty_label.setMinimumHeight(self.LIST_HEIGHT)
        self.empty_label.setMaximumHeight(16777215)
        self.empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_rows(self, rows, *, empty_text="No linked entities"):
        rows = list(rows)
        super().set_rows(rows, empty_text=empty_text)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        if rows:
            self.list.setMinimumHeight(self.LIST_HEIGHT)
            self.list.setMaximumHeight(16777215)
            self.list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.layout.setStretch(self.layout.indexOf(self.list), 1)
        else:
            self.empty_label.setMinimumHeight(self.LIST_HEIGHT)
            self.empty_label.setMaximumHeight(16777215)
            self.empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.layout.setStretch(self.layout.indexOf(self.empty_label), 1)
        self.updateGeometry()


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


class AssessmentStateSummaryCard(CardFrame):
    """Compact Geometry and taller Face condition summary with one Assessment action."""

    open_requested = Signal()
    MINIMUM_WIDTH = 320
    MAXIMUM_WIDTH = 400

    def __init__(self, title="Geometry / face condition", parent=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self.setMinimumWidth(self.MINIMUM_WIDTH)
        self.setMaximumWidth(self.MAXIMUM_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.layout.setContentsMargins(14, 8, 14, 8)
        self.layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        heading = QLabel(tr(title))
        heading.setObjectName("CardTitle")
        self.open_button = OverviewLinkButton("Open ›")
        self.open_button.clicked.connect(self.open_requested)
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self.open_button)
        self.layout.addLayout(header)

        self.sections = QVBoxLayout()
        self.sections.setSpacing(6)
        self.layout.addLayout(self.sections, 1)

    def set_sections(self, sections):
        while self.sections.count():
            item = self.sections.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sections = list(sections)
        for index, (title, lines) in enumerate(sections):
            is_face_condition = index == len(sections) - 1 and len(sections) > 1
            section = QWidget()
            section.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding if is_face_condition else QSizePolicy.Policy.Fixed,
            )
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            heading = QLabel(tr(title))
            heading.setObjectName("EngineeringSectionTitle")
            heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            layout.addWidget(heading)
            text = QLabel(
                "  ·  ".join(str(line) for line in lines if line not in (None, ""))
                or tr("No data yet")
            )
            text.setWordWrap(True)
            text.setObjectName("EngineeringSummaryText")
            text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(text)
            if is_face_condition:
                layout.addStretch(1)
            self.sections.addWidget(section, 1 if is_face_condition else 0)
            if index < len(sections) - 1:
                divider = QFrame()
                divider.setFrameShape(QFrame.Shape.HLine)
                divider.setObjectName("OverviewDivider")
                self.sections.addWidget(divider, 0)


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
