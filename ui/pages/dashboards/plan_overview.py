"""Read-only Project/Domain plan used by compact dashboard overviews."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
    QWheelEvent,
)
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


class DashboardGraphicsView(QGraphicsView):
    clear_filter_requested = Signal()
    MIN_ZOOM_STEPS = -10
    MAX_ZOOM_STEPS = 18
    ZOOM_FACTOR = 1.15

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._zoom_steps = 0

    def reset_zoom_state(self):
        self._zoom_steps = 0

    def mousePressEvent(self, event: QMouseEvent):
        if self.itemAt(event.position().toPoint()) is None:
            self.clear_filter_requested.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.clear_filter_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if not delta:
            event.accept()
            return
        step = 1 if delta > 0 else -1
        next_steps = self._zoom_steps + step
        if next_steps < self.MIN_ZOOM_STEPS or next_steps > self.MAX_ZOOM_STEPS:
            event.accept()
            return
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        factor = self.ZOOM_FACTOR if step > 0 else 1.0 / self.ZOOM_FACTOR
        self.scale(factor, factor)
        self._zoom_steps = next_steps
        event.accept()


class DashboardPlanOverviewWidget(QWidget):
    """Assessment-focused plan with transient Domain/Interval/Area filtering."""

    FRAME_FACTOR = 1.5
    filter_cleared = Signal()

    def __init__(self, snapshot, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.scene = QGraphicsScene(self)
        self.view = DashboardGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setStyleSheet(
            "QGraphicsView{border:1px solid #e4e8ee;border-radius:5px;background:#fbfcfd;}"
        )
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.view.setMinimumHeight(320)
        self.view.clear_filter_requested.connect(self.clear_filter)

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
        self._assessment_entries: list[tuple[QGraphicsPathItem, object]] = []
        self._filter_state: tuple[str, str] | None = None
        self._initial_fit_pending = True
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
        self._filter_state = None
        self._initial_fit_pending = True
        self._render()
        if self.isVisible():
            QTimer.singleShot(0, self._fit_initial_view)

    @staticmethod
    def _normal_assessment_style(item, geometry):
        presentation = assessment_result_presentation(geometry.quadrant)
        border = QColor(presentation.color)
        fill = QColor(presentation.color)
        fill.setAlpha(44 if geometry.quadrant else 24)
        item.setPen(QPen(border, 2.8))
        item.setBrush(QBrush(fill))
        item.setZValue(20)

    @staticmethod
    def _dim_assessment_style(item):
        border = QColor("#aeb8c5")
        border.setAlpha(125)
        fill = QColor("#dbe1e8")
        fill.setAlpha(18)
        item.setPen(QPen(border, 1.0))
        item.setBrush(QBrush(fill))
        item.setZValue(10)

    def _render(self):
        self.scene.clear()
        self._project_items = []
        self._domain_items = []
        self._assessment_items = []
        self._assessment_entries = []

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
            item = QGraphicsPathItem(self._path(geometry.points, close=True))
            self._normal_assessment_style(item, geometry)
            presentation = assessment_result_presentation(geometry.quadrant)
            item.setToolTip(self._assessment_tooltip(geometry, presentation.label))
            self.scene.addItem(item)
            self._assessment_items.append(item)
            self._assessment_entries.append((item, geometry))

        self.empty_label.setVisible(not bool(self.scene.items()))
        self.empty_label.adjustSize()
        self.empty_label.move(16, 16)

    def showEvent(self, event):
        super().showEvent(event)
        self._initial_fit_pending = True
        QTimer.singleShot(0, self._fit_initial_view)
        QTimer.singleShot(60, self._fit_initial_view)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._initial_fit_pending:
            QTimer.singleShot(0, self._fit_initial_view)

    def _fit_initial_view(self):
        if not self._initial_fit_pending or not self.isVisible():
            return
        viewport = self.view.viewport().size()
        if viewport.width() < 50 or viewport.height() < 50:
            QTimer.singleShot(30, self._fit_initial_view)
            return
        self.fit_assessments()
        self._initial_fit_pending = False

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

    @staticmethod
    def _matches_filter(geometry, kind: str, value: str) -> bool:
        if kind == "domain":
            return str(geometry.domain_name) == value
        if kind == "interval":
            return str(geometry.interval) == value
        if kind == "area":
            return str(geometry.entity_id) == value
        return True

    def set_filter(self, kind: str, value):
        state = (str(kind), str(value))
        if self._filter_state == state:
            self.clear_filter()
            return
        self._filter_state = state
        for item, geometry in self._assessment_entries:
            if self._matches_filter(geometry, *state):
                self._normal_assessment_style(item, geometry)
            else:
                self._dim_assessment_style(item)
        self.view.viewport().update()

    def clear_filter(self):
        had_filter = self._filter_state is not None
        self._filter_state = None
        for item, geometry in self._assessment_entries:
            self._normal_assessment_style(item, geometry)
        self.view.viewport().update()
        if had_filter:
            self.filter_cleared.emit()

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
        rect = self._items_rect(self._assessment_items)
        if rect.isNull():
            rect = self._items_rect(self._domain_items)
        if rect.isNull():
            rect = self._items_rect(self._project_items)
        return self._expanded_rect(rect)

    def fit_assessments(self):
        rect = self.focus_rect()
        if not rect.isNull():
            self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.view.reset_zoom_state()


class DashboardPlanCard(DashboardCard):
    primary_action_requested = Signal()
    secondary_action_requested = Signal()
    filter_cleared = Signal()

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
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(405)
        self.setMaximumHeight(455)
        self.header.setSpacing(5)
        self.subtitle.setMaximumWidth(135)

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
        self.plan.filter_cleared.connect(self.filter_cleared)
        self.clear_filter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.clear_filter_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.clear_filter_shortcut.activated.connect(self.plan.clear_filter)

    def set_subtitle(self, text: str | None):
        super().set_subtitle(text)
        self.subtitle.setToolTip(str(text or ""))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return max(405, min(455, int(width * 0.72)))

    def sizeHint(self):
        return QSize(600, 430)

    def set_snapshot(self, snapshot):
        self.plan.set_snapshot(snapshot)

    def set_filter(self, kind: str, value):
        self.plan.set_filter(kind, value)

    def clear_filter(self):
        self.plan.clear_filter()

    def set_actions_enabled(self, enabled: bool):
        if self.primary_action is not None:
            self.primary_action.setEnabled(bool(enabled))
        if self.secondary_action is not None:
            self.secondary_action.setEnabled(bool(enabled))
