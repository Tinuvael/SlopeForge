from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsScene, QGraphicsTextItem

from prototype_2d.connectivity import LineConnection
from prototype_2d.geometry import nearest_point_on_polyline
from prototype_2d.models import DatamineLine, LineSegmentSelection


class LinePathItem(QGraphicsPathItem):
    def __init__(self, line: DatamineLine):
        path = QPainterPath(QPointF(line.points[0].x, -line.points[0].y))
        for point in line.points[1:]:
            path.lineTo(point.x, -point.y)
        super().__init__(path)
        self.line = line
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)


class PrototypePlanScene(QGraphicsScene):
    line_clicked = Signal(str, float, float)

    def __init__(self):
        super().__init__()
        self._items: dict[str, LinePathItem] = {}
        self._lines: list[DatamineLine] = []
        self._segment_items = []
        self._connection_items = []
        self.show_grid = True
        self.active_elevation: float | None = None
        self.only_active_horizon = False
        self.selected_line_id: str | None = None

    def set_lines(self, lines: list[DatamineLine], active_elevation: float | None = None, only_active_horizon: bool = False) -> None:
        self.clear(); self._items.clear(); self._segment_items.clear(); self._connection_items.clear()
        self._lines = lines
        self.active_elevation = active_elevation
        self.only_active_horizon = only_active_horizon
        for line in lines:
            if len(line.points) < 2:
                continue
            if only_active_horizon and active_elevation is not None and line.elevation != active_elevation:
                continue
            item = LinePathItem(line)
            self.addItem(item); self._items[line.source_id] = item
        if self.show_grid:
            self.add_grid()
        self.apply_styles()

    def line_is_active_horizon(self, line: DatamineLine) -> bool:
        if self.active_elevation is None:
            return True
        return line.elevation == self.active_elevation

    def add_grid(self) -> None:
        rect = self.itemsBoundingRect()
        if rect.isNull():
            return
        step = max(rect.width(), rect.height()) / 10 or 100
        pen = QPen(QColor(220, 220, 220), 1, Qt.PenStyle.DotLine)
        x = rect.left()
        while x <= rect.right():
            self.addLine(x, rect.top(), x, rect.bottom(), pen); x += step
        y = rect.top()
        while y <= rect.bottom():
            self.addLine(rect.left(), y, rect.right(), y, pen); y += step

    def apply_styles(self) -> None:
        for key, item in self._items.items():
            if key == self.selected_line_id:
                item.setPen(QPen(QColor(230, 80, 20), 4)); item.setOpacity(1.0); item.setZValue(30)
            elif self.line_is_active_horizon(item.line):
                item.setPen(QPen(QColor(35, 55, 70), 2)); item.setOpacity(1.0); item.setZValue(10)
            else:
                item.setPen(QPen(QColor(170, 170, 170), 1)); item.setOpacity(0.22); item.setZValue(0)

    def set_selected_line(self, source_id: str | None) -> None:
        self.selected_line_id = source_id
        self.apply_styles()
        if source_id and source_id in self._items:
            line = self._items[source_id].line
            text = QGraphicsTextItem(f"SID {line.source_id} · {line.display_elevation()}")
            text.setDefaultTextColor(QColor(230, 80, 20))
            text.setPos(line.points[0].x, -line.points[0].y)
            text.setZValue(40)
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
            item = QGraphicsPathItem(path); item.setPen(QPen(QColor(0, 120, 255), 5)); item.setZValue(50); self.addItem(item); self._segment_items.append(item)
            for point in (segment.extracted_points[0], segment.extracted_points[-1]):
                marker = QGraphicsEllipseItem(point.x - 3, -point.y - 3, 6, 6); marker.setBrush(QColor(0, 120, 255)); marker.setPen(QPen(Qt.GlobalColor.white, 1)); marker.setZValue(60); self.addItem(marker); self._segment_items.append(marker)

    def show_connections(self, connections: list[LineConnection]) -> None:
        for item in self._connection_items:
            self.removeItem(item)
        self._connection_items.clear()
        points = {line.source_id: {"start": line.points[0], "end": line.points[-1]} for line in self._lines if line.points}
        pen = QPen(QColor(130, 60, 200), 1, Qt.PenStyle.DashLine)
        for c in connections:
            a = points.get(c.from_line_id, {}).get(c.from_endpoint); b = points.get(c.to_line_id, {}).get(c.to_endpoint)
            if not a or not b:
                continue
            item = QGraphicsLineItem(a.x, -a.y, b.x, -b.y); item.setPen(pen); item.setZValue(20); self.addItem(item); self._connection_items.append(item)

    def nearest_line_id(self, x: float, y: float) -> str | None:
        best_id = None; best_distance = None
        for line_id, item in self._items.items():
            _point, _position, distance = nearest_point_on_polyline(item.line, x, y)
            if best_distance is None or distance < best_distance:
                best_id = line_id; best_distance = distance
        if best_distance is None:
            return None
        return best_id

    def mousePressEvent(self, event):
        pos = event.scenePos()
        clicked = self.nearest_line_id(pos.x(), -pos.y())
        if clicked:
            self.line_clicked.emit(clicked, pos.x(), -pos.y())
        super().mousePressEvent(event)
