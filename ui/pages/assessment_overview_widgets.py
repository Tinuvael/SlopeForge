from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

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

    def _schedule_row_refit(self) -> None:
        """Assessment owns an expanding viewport, not Block's bounded two-row fit."""

    def _fit_two_rows(self, *, use_visual_geometry=False) -> None:
        """Do not let the base class fix this expanding list's height."""

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
        self.sections.setContentsMargins(0, 8, 0, 0)
        self.sections.setSpacing(8)
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
            layout.setContentsMargins(0, 14 if is_face_condition else 0, 0, 0)
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

    _QUADRANT_COLORS = (
        "#f6df72",  # geometry achieved, condition insufficient
        "#8bd17c",  # good results
        "#ef7770",  # unacceptable
        "#f2b764",  # condition good, geometry unacceptable
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(190, 190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(220, 220)

    def paintEvent(self, event):  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        surface = palette.color(QPalette.ColorRole.AlternateBase)
        border = palette.color(QPalette.ColorRole.Mid)
        text = palette.color(QPalette.ColorRole.WindowText)
        muted = palette.color(QPalette.ColorRole.PlaceholderText)
        point_border = palette.color(QPalette.ColorRole.Base)
        app = QApplication.instance()
        dark = bool(app is not None and app.property("slopeforgeTheme") == "dark")
        accent = QColor("#38bdf8") if dark else palette.color(QPalette.ColorRole.Link)

        side = max(40, min(self.width() - 58, self.height() - 48))
        left = (self.width() - side) / 2
        rect = QRectF(left, 12, side, side)
        painter.fillRect(rect, surface)

        x = rect.left() + rect.width() * self.fci_threshold
        y = rect.bottom() - rect.height() * self.dai_threshold
        regions = (
            QRectF(rect.left(), rect.top(), x - rect.left(), y - rect.top()),
            QRectF(x, rect.top(), rect.right() - x, y - rect.top()),
            QRectF(rect.left(), y, x - rect.left(), rect.bottom() - y),
            QRectF(x, y, rect.right() - x, rect.bottom() - y),
        )
        alpha = 58 if dark else 40
        for region, colour in zip(regions, self._QUADRANT_COLORS):
            fill = QColor(colour)
            fill.setAlpha(alpha)
            painter.fillRect(region, fill)

        painter.setPen(QPen(border, 1.2))
        painter.drawRect(rect)
        separator = QColor(border)
        separator.setAlpha(210 if dark else 180)
        painter.setPen(QPen(separator, 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
        painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))

        painter.setPen(text)
        painter.drawText(int(rect.left()) - 28, int(rect.center().y()), "DAI")
        painter.drawText(int(rect.center().x()) - 8, int(rect.bottom()) + 22, "FCI")
        if self.dai is None or self.fci is None:
            painter.setPen(muted)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, tr("No assessment result yet")
            )
            return

        px = rect.left() + rect.width() * self.fci
        py = rect.bottom() - rect.height() * self.dai
        painter.setPen(QPen(point_border, 2.2))
        painter.setBrush(accent)
        painter.drawEllipse(int(px) - 7, int(py) - 7, 14, 14)


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