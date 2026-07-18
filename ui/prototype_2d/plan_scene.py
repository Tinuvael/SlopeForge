from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene, QGraphicsTextItem

from prototype_2d.models import DatamineLine, LineSegmentSelection


class LinePathItem(QGraphicsPathItem):
    def __init__(self, line: DatamineLine):
        path = QPainterPath(QPointF(line.points[0].x, -line.points[0].y))
        for point in line.points[1:]:
            path.lineTo(point.x, -point.y)
        super().__init__(path)
        self.line = line
        self.setPen(QPen(Qt.GlobalColor.darkGray, 0))
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)


class PrototypePlanScene(QGraphicsScene):
    line_clicked = Signal(str, float, float)

    def __init__(self):
        super().__init__()
        self._items: dict[str, LinePathItem] = {}
        self._segment_items = []

    def set_lines(self, lines: list[DatamineLine]) -> None:
        self.clear(); self._items.clear(); self._segment_items.clear()
        for line in lines:
            if len(line.points) < 2:
                continue
            item = LinePathItem(line)
            self.addItem(item); self._items[line.source_id] = item
        self.add_grid()

    def add_grid(self) -> None:
        rect = self.itemsBoundingRect()
        if rect.isNull():
            return
        step = max(rect.width(), rect.height()) / 10 or 100
        pen = QPen(Qt.GlobalColor.lightGray, 0, Qt.PenStyle.DotLine)
        x = rect.left()
        while x <= rect.right():
            self.addLine(x, rect.top(), x, rect.bottom(), pen); x += step
        y = rect.top()
        while y <= rect.bottom():
            self.addLine(rect.left(), y, rect.right(), y, pen); y += step

    def set_selected_line(self, source_id: str | None) -> None:
        for key, item in self._items.items():
            item.setPen(QPen(Qt.GlobalColor.red if key == source_id else Qt.GlobalColor.darkGray, 0 if key != source_id else 2))
        if source_id and source_id in self._items:
            line = self._items[source_id].line
            text = QGraphicsTextItem(f"PTN {line.source_id} · Z {line.elevation}")
            text.setPos(line.points[0].x, -line.points[0].y)
            self.addItem(text)

    def show_segments(self, segments: list[LineSegmentSelection]) -> None:
        for item in self._segment_items:
            self.removeItem(item)
        self._segment_items.clear()
        for segment in segments:
            if len(segment.extracted_points) < 2:
                continue
            path = QPainterPath(QPointF(segment.extracted_points[0].x, -segment.extracted_points[0].y))
            for point in segment.extracted_points[1:]:
                path.lineTo(point.x, -point.y)
            item = QGraphicsPathItem(path); item.setPen(QPen(Qt.GlobalColor.blue, 3)); self.addItem(item); self._segment_items.append(item)
            for point in (segment.extracted_points[0], segment.extracted_points[-1]):
                marker = QGraphicsEllipseItem(point.x - 2, -point.y - 2, 4, 4); marker.setPen(QPen(Qt.GlobalColor.blue, 0)); self.addItem(marker); self._segment_items.append(marker)

    def mousePressEvent(self, event):
        pos = event.scenePos()
        clicked = None
        for item in self.items(pos):
            if isinstance(item, LinePathItem):
                clicked = item.line.source_id; break
        if clicked:
            self.line_clicked.emit(clicked, pos.x(), -pos.y())
        super().mousePressEvent(event)
