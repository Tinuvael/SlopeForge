from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView


class PrototypePlanView(QGraphicsView):
    cursor_moved = Signal(float, float)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, event):
        self.scale(1.15 if event.angleDelta().y() > 0 else 1 / 1.15, 1.15 if event.angleDelta().y() > 0 else 1 / 1.15)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        self.cursor_moved.emit(pos.x(), -pos.y())
        super().mouseMoveEvent(event)

    def fit_to_extent(self):
        rect = self.scene().itemsBoundingRect()
        if not rect.isNull():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
