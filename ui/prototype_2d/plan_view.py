from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView


class PrototypePlanView(QGraphicsView):
    cursor_moved = Signal(float, float)
    escape_requested = Signal()
    workflow_key_requested = Signal(str)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

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

    def fit_to_extent(self):
        rect = self.scene().itemsBoundingRect()
        if not rect.isNull(): self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
