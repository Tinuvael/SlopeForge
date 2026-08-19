"""Read-only Project/Domain plan used by compact dashboard overviews."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.localization import tr
from ui.assessment_result_presentation import assessment_result_presentation
from ui.pages.entity_overview_widgets import OverviewLinkButton
from .widgets import DashboardCard, metric


class DashboardPlanOverviewWidget(QWidget):
    """Assessment-focused plan with Project Lines and optional Domain context."""

    FRAME_FACTOR = 1.5

    def __init__(self, snapshot, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setStyleSheet(
            "QGraphicsView{border:1px solid #e4e8ee;border-radius:5px;background:#fbfcfd;}"
        )
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.view.setMinimumHeight(245)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)

        self.empty_label = QLabel(tr("No plan geometry yet"), self.view.viewport())
        self.empty_label.setObjectName("MutedText")
        self.empty_label.setStyleSheet("background:transparent;")
        self.empty_label.hide()

        self._project_items: list[QGraphicsPathItem] = []
        self._domain_items: list[QGraphicsPathItem] = []
        self._assessment_items: list[QGraphicsPathItem] = []
        self._render()

    @staticmethod
    def _path(points, *, close=False):
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0][0], -points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, -y)
        if close:
            path.closeSubpath()
        return path

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        self._render()

    def _render(self):
        self.scene.clear()
        self._project_items = []
        self._domain_items = []
        self._assessment_items = []

        for geometry in getattr(self.snapshot, "domain_geometries", ()):
            path = self._path(geometry.points, close=True)
            item = QGraphicsPathItem(path)
            if geometry.is_current:
                pen = QColor("#94a3b8")
                fill = QColor("#cbd5e1")
                pen.setAlpha(125)
                fill.setAlpha(28)
                width = 1.6
            else:
                pen = QColor("#cbd5e1")
                fill = QColor("#e2e8f0")
                pen.setAlpha(75)
                fill.setAlpha(14)
                width = 1.0
            item.setPen(QPen(pen, width))
            item.setBrush(QBrush(fill))
            item.setZValue(-20)
            item.setToolTip(str(geometry.domain_name))
            self.scene.addItem(item)
            self._domain_items.append(item)

        for geometry in getattr(self.snapshot, "project_lines", ()):
            item = QGraphicsPathItem(self._path(geometry.points, close=False))
            item.setPen(QPen(QColor("#c5ccd5"), 1.0))
            item.setZValue(-10)
            self.scene.addItem(item)
            self._project_items.append(item)

        for geometry in getattr(self.snapshot, "assessment_geometries", ()):
            presentation = assessment_result_presentation(geometry.quadrant)
            border = QColor(presentation.color)
            fill = QColor(presentation.color)
            fill.setAlpha(44 if geometry.quadrant else 24)
            item = QGraphicsPathItem(self._path(geometry.points, close=True))
            item.setPen(QPen(border, 2.8))
            item.setBrush(QBrush(fill))
            item.setZValue(20)
            item.setToolTip(self._assessment_tooltip(geometry, presentation.label))
            self.scene.addItem(item)
            self._assessment_items.append(item)

        self.empty_label.setVisible(not bool(self.scene.items()))
        self.empty_label.adjustSize()
        self.empty_label.move(16, 16)
        self.fit_assessments()

    @staticmethod
    def _assessment_tooltip(geometry, result_label: str) -> str:
        lines = [geometry.name or str(geometry.entity_id)]
        if geometry.domain_name:
            lines.append(f"{tr('Domain')}: {geometry.domain_name}")
        if geometry.interval:
            lines.append(f"{tr('Interval')}: {geometry.interval}")
        if geometry.dai is not None:
            lines.append(f"DAI: {metric(geometry.dai)}")
        if geometry.fci is not None:
            lines.append(f"FCI: {metric(geometry.fci)}")
        lines.append(f"{tr('Result')}: {result_label}")
        return "\n".join(lines)

    def set_project_lines_visible(self, visible: bool):
        for item in self._project_items:
            item.setVisible(bool(visible))
        self.fit_assessments()

    @staticmethod
    def _items_rect(items) -> QRectF:
        rect = QRectF()
        for item in items:
            if not item.isVisible():
                continue
            item_rect = item.sceneBoundingRect()
            rect = item_rect if rect.isNull() else rect.united(item_rect)
        return rect

    @classmethod
    def _expanded_rect(cls, rect: QRectF) -> QRectF:
        if rect.isNull():
            return rect
        width = max(rect.width(), 1.0) * cls.FRAME_FACTOR
        height = max(rect.height(), 1.0) * cls.FRAME_FACTOR
        center = rect.center()
        return QRectF(
            center.x() - width / 2,
            center.y() - height / 2,
            width,
            height,
        )

    def focus_rect(self) -> QRectF:
        # Assessment Areas are the operational focus. Domain geometry is context;
        # Project Lines are only a final fallback when no area/boundary exists.
        rect = self._items_rect(self._assessment_items)
        if rect.isNull():
            rect = self._items_rect(self._domain_items)
        if rect.isNull():
            rect = self._items_rect(self._project_items)
        return self._expanded_rect(rect)

    def fit_assessments(self):
        rect = self.focus_rect()
        if not rect.isNull():
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


class DashboardPlanCard(DashboardCard):
    """Compact dashboard plan with a stable near-4:3 sizing contract."""

    primary_action_requested = Signal()
    secondary_action_requested = Signal()

    def __init__(
        self,
        snapshot,
        *,
        title="Plan / assessment areas",
        primary_action_label: str | None = None,
        secondary_action_label: str | None = None,
        parent=None,
    ):
        super().__init__(title, parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(440)
        self.setMaximumWidth(560)
        self.setMinimumHeight(310)
        self.setMaximumHeight(370)

        self.lines = QCheckBox(tr("Project Lines"))
        self.lines.setChecked(True)
        self.header.addWidget(self.lines)
        self.center_button = OverviewLinkButton("Center")
        self.header.addWidget(self.center_button)

        self.primary_action = None
        if primary_action_label:
            self.primary_action = OverviewLinkButton(primary_action_label)
            self.primary_action.clicked.connect(self.primary_action_requested)
            self.header.addWidget(self.primary_action)

        self.secondary_action = None
        if secondary_action_label:
            self.secondary_action = OverviewLinkButton(secondary_action_label)
            self.secondary_action.clicked.connect(self.secondary_action_requested)
            self.header.addWidget(self.secondary_action)

        self.plan = DashboardPlanOverviewWidget(snapshot, self)
        self.layout.addWidget(self.plan, 1)
        self.lines.toggled.connect(self.plan.set_project_lines_visible)
        self.center_button.clicked.connect(self.plan.fit_assessments)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return max(310, min(370, int(width * 0.69)))

    def sizeHint(self):
        return QSize(510, 350)

    def set_snapshot(self, snapshot):
        self.plan.set_snapshot(snapshot)

    def set_actions_enabled(self, enabled: bool):
        if self.primary_action is not None:
            self.primary_action.setEnabled(bool(enabled))
        if self.secondary_action is not None:
            self.secondary_action.setEnabled(bool(enabled))
