from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView
from prototype_2d.domain import PlanPoint


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
        self.setMouseTracking(True)
        self._drawing_mode = False

    def set_polygon_drawing_mode(self, enabled: bool):
        self._drawing_mode = enabled
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
        pos = self.mapToScene(event.position().toPoint())
        self.cursor_moved.emit(pos.x(), -pos.y())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if self._drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            point = self.scene_to_domain(self.mapToScene(event.position().toPoint()))
            self.scene_clicked.emit(point.x, point.y)
            event.accept()
            return
        super().mousePressEvent(event)

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
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)
