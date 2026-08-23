from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.localization import tr
from domain.blasting.drillhole_selection import hole_ids_in_polygon
from ui.widgets.design_system import configure_standard_dialog, set_button_role


HOLE_ID_ROLE = 0


class DrillholeSelectionView(QGraphicsView):
    selection_changed = Signal()
    polygon_state_changed = Signal(bool)

    def __init__(self, holes, selected_ids=(), plan_geometry=None, parent=None):
        super().__init__(parent)
        self.holes = tuple(holes)
        self.selected_ids = set(selected_ids)
        self.mode = "individual"
        self._polygon_points: list[tuple[float, float]] = []
        self._hole_items: dict[str, QGraphicsEllipseItem] = {}
        self._polygon_preview: QGraphicsPathItem | None = None
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(self.renderHints().Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._render(plan_geometry)

    @staticmethod
    def _scene_point(x: float, y: float) -> QPointF:
        return QPointF(float(x), -float(y))

    def _extent(self, plan_geometry):
        points = [(hole.collar.x, hole.collar.y) for hole in self.holes]
        ring = getattr(plan_geometry, "ring", ()) if plan_geometry is not None else ()
        points.extend((point.x, point.y) for point in ring)
        if not points:
            return 1.0
        xs = [item[0] for item in points]
        ys = [item[1] for item in points]
        return max(max(xs) - min(xs), max(ys) - min(ys), 1.0)

    def _render(self, plan_geometry):
        self.scene().clear()
        self._hole_items = {}
        ring = getattr(plan_geometry, "ring", ()) if plan_geometry is not None else ()
        if ring:
            path = QPainterPath()
            first = self._scene_point(ring[0].x, ring[0].y)
            path.moveTo(first)
            for point in ring[1:]:
                path.lineTo(self._scene_point(point.x, point.y))
            outline = self.scene().addPath(path, QPen(QColor("#7b8794"), 1.4))
            outline.setZValue(0)

        radius = min(max(self._extent(plan_geometry) * 0.008, 0.35), 4.0)
        for hole in self.holes:
            center = self._scene_point(hole.collar.x, hole.collar.y)
            item = QGraphicsEllipseItem(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
            )
            item.setData(HOLE_ID_ROLE, hole.hole_id)
            item.setToolTip(
                f"{hole.hole_id}\nX {hole.collar.x:.3f}  Y {hole.collar.y:.3f}  Z {hole.collar.z:.3f}"
            )
            item.setZValue(5)
            self.scene().addItem(item)
            self._hole_items[hole.hole_id] = item
        self._refresh_hole_styles()
        bounds = self.scene().itemsBoundingRect()
        if not bounds.isNull():
            margin = max(bounds.width(), bounds.height()) * 0.05
            self.scene().setSceneRect(bounds.adjusted(-margin, -margin, margin, margin))
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _refresh_hole_styles(self):
        for hole in self.holes:
            item = self._hole_items.get(hole.hole_id)
            if item is None:
                continue
            if hole.hole_id in self.selected_ids:
                item.setPen(QPen(QColor("#0b63ce"), 1.6))
                item.setBrush(QBrush(QColor("#5b9bea")))
            elif hole.engineering_group_id:
                item.setPen(QPen(QColor("#8a5a00"), 1.5))
                item.setBrush(QBrush(QColor("#fff4d6")))
            else:
                item.setPen(QPen(QColor("#64748b"), 1.2))
                item.setBrush(QBrush(QColor("#ffffff")))

    def set_mode(self, mode: str):
        if mode not in {"individual", "polygon"}:
            raise ValueError(mode)
        self.mode = mode
        self._polygon_points.clear()
        self._clear_polygon_preview()
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag
            if mode == "polygon"
            else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.polygon_state_changed.emit(False)

    def clear_selection(self):
        self.selected_ids.clear()
        self._refresh_hole_styles()
        self.selection_changed.emit()

    def select_all(self):
        self.selected_ids = {hole.hole_id for hole in self.holes}
        self._refresh_hole_styles()
        self.selection_changed.emit()

    def _toggle_item_at(self, viewport_pos):
        item = self.itemAt(viewport_pos)
        hole_id = item.data(HOLE_ID_ROLE) if item is not None else None
        if not hole_id:
            return False
        hole_id = str(hole_id)
        if hole_id in self.selected_ids:
            self.selected_ids.remove(hole_id)
        else:
            self.selected_ids.add(hole_id)
        self._refresh_hole_styles()
        self.selection_changed.emit()
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == "individual":
                if self._toggle_item_at(event.position().toPoint()):
                    return
            else:
                point = self.mapToScene(event.position().toPoint())
                self._polygon_points.append((point.x(), -point.y()))
                self._update_polygon_preview()
                self.polygon_state_changed.emit(len(self._polygon_points) >= 3)
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.mode == "polygon" and event.button() == Qt.MouseButton.LeftButton:
            self.complete_polygon()
            return
        super().mouseDoubleClickEvent(event)

    def _clear_polygon_preview(self):
        if self._polygon_preview is not None:
            self.scene().removeItem(self._polygon_preview)
            self._polygon_preview = None

    def _update_polygon_preview(self):
        self._clear_polygon_preview()
        if not self._polygon_points:
            return
        path = QPainterPath()
        first = self._scene_point(*self._polygon_points[0])
        path.moveTo(first)
        for x, y in self._polygon_points[1:]:
            path.lineTo(self._scene_point(x, y))
        if len(self._polygon_points) >= 3:
            path.lineTo(first)
        self._polygon_preview = self.scene().addPath(
            path,
            QPen(QColor("#0b63ce"), 1.5, Qt.PenStyle.DashLine),
        )
        self._polygon_preview.setZValue(10)

    def complete_polygon(self):
        if len(self._polygon_points) < 3:
            return
        self.selected_ids.update(hole_ids_in_polygon(self.holes, self._polygon_points))
        self._polygon_points.clear()
        self._clear_polygon_preview()
        self._refresh_hole_styles()
        self.polygon_state_changed.emit(False)
        self.selection_changed.emit()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class DrillholeGroupAssignmentDialog(QDialog):
    def __init__(self, group_name, holes, *, selected_ids=(), plan_geometry=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Assign drillholes"))
        layout = configure_standard_dialog(self, minimum_width=980)

        heading = QLabel(
            tr("Assign design drillholes to %1").replace("%1", str(group_name))
        )
        heading.setObjectName("EntityTitle")
        layout.addWidget(heading)

        body = QHBoxLayout()
        self.view = DrillholeSelectionView(
            holes,
            selected_ids=selected_ids,
            plan_geometry=plan_geometry,
            parent=self,
        )
        self.view.setMinimumSize(700, 520)
        body.addWidget(self.view, 1)

        controls_host = QWidget()
        controls = QVBoxLayout(controls_host)
        controls.setContentsMargins(8, 0, 0, 0)
        controls.setSpacing(8)
        mode_title = QLabel(tr("Selection mode"))
        mode_title.setObjectName("CardTitle")
        controls.addWidget(mode_title)
        self.individual = set_button_role(QPushButton(tr("Select individually")), "secondary")
        self.polygon = set_button_role(QPushButton(tr("Select by polygon")), "secondary")
        self.finish_polygon = set_button_role(QPushButton(tr("Finish polygon")), "secondary")
        self.finish_polygon.setEnabled(False)
        self.clear = set_button_role(QPushButton(tr("Clear selection")), "secondary")
        self.select_all = set_button_role(QPushButton(tr("Select all")), "secondary")
        for button in (self.individual, self.polygon, self.finish_polygon, self.clear, self.select_all):
            controls.addWidget(button)
        self.count = QLabel()
        self.count.setObjectName("SummaryValue")
        controls.addSpacing(8)
        controls.addWidget(self.count)
        help_text = QLabel(
            tr("Individual: click hole collars. Polygon: click at least three vertices, then Finish polygon or double-click. Yellow holes are assigned to another group; selecting them moves them to this group.")
        )
        help_text.setObjectName("MutedText")
        help_text.setWordWrap(True)
        controls.addWidget(help_text)
        controls.addStretch()
        body.addWidget(controls_host, 0)
        layout.addLayout(body, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = set_button_role(QPushButton(tr("Cancel")), "secondary")
        apply_button = set_button_role(QPushButton(tr("Apply")), "primary")
        cancel.clicked.connect(self.reject)
        apply_button.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(apply_button)
        layout.addLayout(actions)

        self.individual.clicked.connect(lambda: self.view.set_mode("individual"))
        self.polygon.clicked.connect(lambda: self.view.set_mode("polygon"))
        self.finish_polygon.clicked.connect(self.view.complete_polygon)
        self.clear.clicked.connect(self.view.clear_selection)
        self.select_all.clicked.connect(self.view.select_all)
        self.view.selection_changed.connect(self._update_count)
        self.view.polygon_state_changed.connect(self.finish_polygon.setEnabled)
        self._update_count()

    def _update_count(self):
        self.count.setText(
            tr("Selected: %1 / %2")
            .replace("%1", str(len(self.view.selected_ids)))
            .replace("%2", str(len(self.view.holes)))
        )

    @property
    def selected_hole_ids(self) -> set[str]:
        return set(self.view.selected_ids)
