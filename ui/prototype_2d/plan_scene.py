from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsScene, QGraphicsTextItem

from prototype_2d.geometry import extract_segment, nearest_point_on_polyline
from prototype_2d.models import DatamineLine, LineSegmentSelection
from prototype_2d.occupancy import OccupiedInterval


class LinePathItem(QGraphicsPathItem):
    def __init__(self, line: DatamineLine):
        path = QPainterPath(QPointF(line.points[0].x, -line.points[0].y))
        for point in line.points[1:]:
            path.lineTo(point.x, -point.y)
        super().__init__(path)
        self.line = line


class SegmentMarkerItem(QGraphicsEllipseItem):
    def __init__(self, marker: str, point, label: str):
        super().__init__(-6, -6, 12, 12)
        self.marker = marker
        self.setPos(point.x, -point.y)
        self.setBrush(QColor(255, 210, 0))
        self.setPen(QPen(QColor(40, 40, 40), 2))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setZValue(80)
        self.text = QGraphicsTextItem(label, self)
        self.text.setPos(8, -20)
        self.text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            self.scene().marker_dragged.emit(self.marker, value.x(), -value.y())
        return super().itemChange(change, value)


class PrototypePlanScene(QGraphicsScene):
    line_clicked = Signal(str, float, float)
    line_hovered = Signal(float, float)
    marker_moved = Signal(str, float, float)
    marker_dragged = Signal(str, float, float)
    line_context_requested = Signal(str, object)

    def __init__(self):
        super().__init__()
        self._items: dict[str, LinePathItem] = {}
        self._lines: list[DatamineLine] = []
        self._segment_items = []
        self._preview_items = []
        self._marker_items: dict[str, SegmentMarkerItem] = {}
        self._occupied_items = []
        self.show_grid = True
        self.active_elevation: float | None = None
        self.only_active_horizon = False
        self.selected_line_id: str | None = None
        self.active_line_id: str | None = None
        self._horizon_label: QGraphicsTextItem | None = None

    def set_lines(self, lines: list[DatamineLine], active_elevation: float | None = None, only_active_horizon: bool = False) -> None:
        self.clear(); self._horizon_label = None; self._items.clear(); self._segment_items.clear(); self._preview_items.clear(); self._marker_items.clear(); self._occupied_items.clear()
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
        self.set_horizon_label(active_elevation)

    def set_horizon_label(self, elevation: float | None) -> None:
        if self._horizon_label is not None:
            self.removeItem(self._horizon_label)
        title = "Рабочий горизонт\n" + (f"{elevation:g}" if elevation is not None else "Все отметки")
        label = QGraphicsTextItem(title)
        label.setDefaultTextColor(QColor(40, 40, 40))
        label.setZValue(100)
        rect = self.itemsBoundingRect()
        label.setPos(rect.left() + max(5, rect.width() * 0.02), rect.top() + max(5, rect.height() * 0.02))
        self.addItem(label)
        self._horizon_label = label

    def set_active_line(self, source_id: str | None) -> None:
        self.active_line_id = source_id
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
            if self.active_line_id and key != self.active_line_id:
                item.setPen(QPen(QColor(170, 170, 170), 0.6)); item.setOpacity(0.12); item.setZValue(0)
            elif key == self.selected_line_id:
                item.setPen(QPen(QColor(230, 80, 20), 2.5)); item.setOpacity(1.0); item.setZValue(30)
            elif key == self.active_line_id:
                item.setPen(QPen(QColor(20, 110, 220), 2.5)); item.setOpacity(1.0); item.setZValue(25)
            elif item.line.semantic_role == "pit_boundary":
                item.setPen(QPen(QColor(45, 35, 25), 1.8)); item.setOpacity(0.9); item.setZValue(15)
            elif self.line_is_active_horizon(item.line):
                item.setPen(QPen(QColor(35, 55, 70), 1.2)); item.setOpacity(1.0); item.setZValue(10)
            else:
                item.setPen(QPen(QColor(170, 170, 170), 0.5)); item.setOpacity(0.22); item.setZValue(0)

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

    def show_segments(self, segments: list[LineSegmentSelection], selected_segment_id: str | None = None) -> None:
        for item in self._segment_items:
            self.removeItem(item)
        self._segment_items.clear()
        colors = {"lower_boundary": QColor(20, 150, 80), "upper_boundary": QColor(190, 70, 220), "intermediate_assessment": QColor(0, 120, 255)}
        for segment in segments:
            if len(segment.extracted_points) < 2:
                continue
            path = QPainterPath(QPointF(segment.extracted_points[0].x, -segment.extracted_points[0].y))
            for point in segment.extracted_points[1:]:
                path.lineTo(point.x, -point.y)
            item = QGraphicsPathItem(path); item.setPen(QPen(QColor(255, 130, 0) if segment.id == selected_segment_id else colors.get(segment.role, QColor(0, 120, 255)), 4 if segment.id == selected_segment_id else 2.8)); item.setZValue(60 if segment.id == selected_segment_id else 50); self.addItem(item); self._segment_items.append(item)

    def clear_preview(self) -> None:
        for item in [*self._preview_items, *self._marker_items.values()]:
            self.removeItem(item)
        self._preview_items.clear(); self._marker_items.clear()

    def update_drag_preview(self, line: DatamineLine, start_position: float | None, end_position: float | None, invalid: bool = False) -> None:
        """Обновляет только полосу preview, не удаляя захваченные мышью A/B."""
        for item in self._preview_items:
            self.removeItem(item)
        self._preview_items.clear()
        if start_position is None or end_position is None:
            return
        _start, _end, points = extract_segment(line, start_position, end_position)
        path = QPainterPath(QPointF(points[0].x, -points[0].y))
        for point in points[1:]: path.lineTo(point.x, -point.y)
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(210, 45, 45) if invalid else QColor(255, 130, 0), 3.5))
        item.setZValue(70); self.addItem(item); self._preview_items.append(item)

    def show_segment_preview(self, line: DatamineLine, start_position: float | None, end_position: float | None, invalid: bool = False) -> None:
        self.clear_preview()
        if start_position is None:
            return
        start_point = nearest_point_on_polyline(line, *self.point_xy(line, start_position))[0]
        self.add_marker("start", start_point, "A")
        if end_position is None:
            return
        _s, _e, points = extract_segment(line, start_position, end_position)
        path = QPainterPath(QPointF(points[0].x, -points[0].y))
        for point in points[1:]:
            path.lineTo(point.x, -point.y)
        item = QGraphicsPathItem(path); item.setPen(QPen(QColor(210, 45, 45) if invalid else QColor(255, 130, 0), 3.5)); item.setZValue(70); self.addItem(item); self._preview_items.append(item)
        self.add_marker("end", points[-1], "B")

    def point_xy(self, line: DatamineLine, position: float) -> tuple[float, float]:
        from prototype_2d.geometry import point_at_position
        point = point_at_position(line, position)
        return point.x, point.y

    def add_marker(self, marker: str, point, label: str) -> None:
        item = SegmentMarkerItem(marker, point, label)
        self.addItem(item)
        self._marker_items[marker] = item

    def show_occupied_intervals(self, line: DatamineLine | None, intervals: list[OccupiedInterval]) -> None:
        for item in self._occupied_items:
            self.removeItem(item)
        self._occupied_items.clear()
        if not line:
            return
        for interval in intervals:
            _start, _end, points = extract_segment(line, interval.start, interval.end)
            if len(points) < 2:
                continue
            path = QPainterPath(QPointF(points[0].x, -points[0].y))
            for point in points[1:]:
                path.lineTo(point.x, -point.y)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(QColor(210, 45, 45), 3))
            item.setOpacity(0.55)
            item.setZValue(45)
            item.setToolTip(interval.description())
            self.addItem(item)
            self._occupied_items.append(item)

    def nearest_line_candidates(self, x: float, y: float, limit: int = 4) -> list[tuple[str, float]]:
        candidates = []
        iterable = self._items.items()
        if self.active_line_id:
            iterable = [(self.active_line_id, self._items[self.active_line_id])] if self.active_line_id in self._items else []
        for line_id, item in iterable:
            _point, _position, distance = nearest_point_on_polyline(item.line, x, y)
            candidates.append((line_id, distance))
        candidates.sort(key=lambda item: item[1])
        return candidates[:limit]

    def nearest_line_id(self, x: float, y: float) -> str | None:
        candidates = self.nearest_line_candidates(x, y, 1)
        return candidates[0][0] if candidates else None

    def mouseMoveEvent(self, event):
        pos = event.scenePos()
        self.line_hovered.emit(pos.x(), -pos.y())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        pos = event.scenePos()
        if event.button() == Qt.MouseButton.RightButton:
            clicked = self.nearest_line_id(pos.x(), -pos.y())
            if clicked:
                self.line_context_requested.emit(clicked, event.screenPos())
            event.accept()
            return
        if isinstance(self.itemAt(pos, self.views()[0].transform() if self.views() else QTransform()), SegmentMarkerItem):
            super().mousePressEvent(event)
            return
        clicked = self.nearest_line_id(pos.x(), -pos.y())
        if clicked:
            self.line_clicked.emit(clicked, pos.x(), -pos.y())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        for marker, item in self._marker_items.items():
            if item.isUnderMouse():
                pos = item.scenePos()
                self.marker_moved.emit(marker, pos.x(), -pos.y())
        super().mouseReleaseEvent(event)
