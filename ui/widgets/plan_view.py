from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QPainter
from PySide6.QtWidgets import QGraphicsView
from domain.geometry.types import PlanPoint


class PrototypePlanView(QGraphicsView):
    cursor_moved = Signal(float, float)
    escape_requested = Signal()
    workflow_key_requested = Signal(str)
    scene_clicked = Signal(float, float)
    scene_double_clicked = Signal(float, float)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self._drawing_mode = False
        self._middle_panning = False
        self._pan_view_position = None

    def set_polygon_drawing_mode(self, enabled: bool):
        self._drawing_mode = enabled
        # Left click belongs to the boundary while drawing.  Middle-drag is
        # always available for navigation and is handled explicitly below.
        self.setDragMode(QGraphicsView.DragMode.NoDrag if enabled else QGraphicsView.DragMode.ScrollHandDrag)
        if enabled:
            self.setFocus()

    def set_polygon_refinement_mode(self):
        """Disable viewport panning while movable scene handles are active."""
        self._drawing_mode = False
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFocus()

    @staticmethod
    def scene_to_domain(point):
        return PlanPoint(point.x(), -point.y())

    def wheelEvent(self, event):
        scale = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(scale, scale)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape: self.escape_requested.emit(); event.accept(); return
        if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}: self.workflow_key_requested.emit("enter"); event.accept(); return
        if key == Qt.Key.Key_Backspace: self.workflow_key_requested.emit("back"); event.accept(); return
        if key == Qt.Key.Key_Delete: self.workflow_key_requested.emit("delete"); event.accept(); return
        if key in {Qt.Key.Key_Up, Qt.Key.Key_Left}: self.workflow_key_requested.emit("candidate_previous"); event.accept(); return
        if key in {Qt.Key.Key_Down, Qt.Key.Key_Right}: self.workflow_key_requested.emit("candidate_next"); event.accept(); return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        if self._middle_panning and self._pan_view_position is not None:
            current = event.position().toPoint()
            delta = current - self._pan_view_position
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_view_position = current
            event.accept()
            return
        pos = self.mapToScene(event.position().toPoint())
        self.cursor_moved.emit(pos.x(), -pos.y())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_panning = True
            self._pan_view_position = event.position().toPoint()
            self.viewport().setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return
        if self._drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            point = self.scene_to_domain(self.mapToScene(event.position().toPoint()))
            self.scene_clicked.emit(point.x, point.y)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._middle_panning:
            self._middle_panning = False
            self._pan_view_position = None
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            point = self.scene_to_domain(self.mapToScene(event.position().toPoint()))
            self.scene_double_clicked.emit(point.x, point.y)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def fit_to_extent(self):
        rect = self.scene().itemsBoundingRect()
        if not rect.isNull():
            margin = max(min(max(rect.width(), rect.height()) * 0.03, 100.0), 1.0)
            self.fit_to_rect(rect.adjusted(-margin, -margin, margin, margin))

    def fit_to_rect(self, rect):
        """Use one aspect-ratio-preserving framing path for every plan view."""
        if not rect.isNull():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
