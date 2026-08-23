from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.localization import tr
from domain.blasting.drillhole_selection import hole_ids_in_polygon
from ui.theme import Color, Spacing
from ui.widgets.design_system import configure_standard_dialog, set_button_role


HOLE_ID_ROLE = 0


class DrillholeSelectionView(QGraphicsView):
    selection_changed = Signal()
    polygon_state_changed = Signal(bool)

    def __init__(
        self,
        holes,
        selected_ids=(),
        plan_geometry=None,
        *,
        group_labels=None,
        parent=None,
    ):
        super().__init__(parent)
        self.holes = tuple(holes)
        self.selected_ids = set(selected_ids)
        self.group_labels = dict(group_labels or {})
        self.mode = "individual"
        self._polygon_points: list[tuple[float, float]] = []
        self._hole_items: dict[str, QGraphicsEllipseItem] = {}
        self._polygon_preview: QGraphicsPathItem | None = None
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
            outline = self.scene().addPath(path, QPen(QColor(Color.TEXT_MUTED), 1.4))
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
            assignment = ""
            if hole.engineering_group_id:
                group_name = self.group_labels.get(
                    hole.engineering_group_id,
                    tr("another drilling group"),
                )
                assignment = f"\n{tr('Assigned to')}: {group_name}"
            item.setToolTip(
                f"{hole.hole_id}\n"
                f"X {hole.collar.x:.3f}  Y {hole.collar.y:.3f}  Z {hole.collar.z:.3f}"
                f"{assignment}"
            )
            item.setZValue(5)
            self.scene().addItem(item)
            self._hole_items[hole.hole_id] = item
        self._refresh_hole_styles()
        bounds = self.scene().itemsBoundingRect()
        if not bounds.isNull():
            margin = max(bounds.width(), bounds.height()) * 0.05
            self.scene().setSceneRect(bounds.adjusted(-margin, -margin, margin, margin))
            self.fit_all()

    def _refresh_hole_styles(self):
        for hole in self.holes:
            item = self._hole_items.get(hole.hole_id)
            if item is None:
                continue
            if hole.hole_id in self.selected_ids:
                item.setPen(QPen(QColor(Color.ACCENT), 1.8))
                item.setBrush(QBrush(QColor(Color.SELECTED)))
            elif hole.engineering_group_id:
                item.setPen(QPen(QColor(Color.WARNING), 1.6))
                item.setBrush(QBrush(QColor(Color.SURFACE)))
            else:
                item.setPen(QPen(QColor(Color.TEXT_MUTED), 1.2))
                item.setBrush(QBrush(QColor(Color.SURFACE)))

    def fit_all(self):
        rect = self.scene().sceneRect()
        if not rect.isNull():
            self.resetTransform()
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def set_mode(self, mode: str):
        if mode not in {"individual", "polygon"}:
            raise ValueError(mode)
        self.mode = mode
        self.cancel_polygon()
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag
            if mode == "polygon"
            else QGraphicsView.DragMode.ScrollHandDrag
        )

    def cancel_polygon(self):
        self._polygon_points.clear()
        self._clear_polygon_preview()
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

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self.select_all()
            return
        if event.key() == Qt.Key.Key_Escape and self._polygon_points:
            self.cancel_polygon()
            return
        super().keyPressEvent(event)

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
            QPen(QColor(Color.ACCENT), 1.5, Qt.PenStyle.DashLine),
        )
        self._polygon_preview.setZValue(10)

    def complete_polygon(self):
        if len(self._polygon_points) < 3:
            return
        self.selected_ids.update(hole_ids_in_polygon(self.holes, self._polygon_points))
        self.cancel_polygon()
        self._refresh_hole_styles()
        self.selection_changed.emit()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class DrillholeGroupAssignmentDialog(QDialog):
    def __init__(
        self,
        group_name,
        holes,
        *,
        selected_ids=(),
        plan_geometry=None,
        group_labels=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("Assign drillholes"))
        layout = configure_standard_dialog(self, minimum_width=900)
        self.resize(1080, 680)

        heading = QLabel(
            tr("Assign design drillholes to %1").replace("%1", str(group_name))
        )
        heading.setObjectName("EntityTitle")
        layout.addWidget(heading)

        self.instruction = QLabel()
        self.instruction.setObjectName("FormHelperText")
        self.instruction.setWordWrap(True)
        layout.addWidget(self.instruction)

        body = QHBoxLayout()
        body.setSpacing(Spacing.MD)
        self.view = DrillholeSelectionView(
            holes,
            selected_ids=selected_ids,
            plan_geometry=plan_geometry,
            group_labels=group_labels,
            parent=self,
        )
        self.view.setMinimumSize(620, 430)
        body.addWidget(self.view, 1)

        controls_host = QWidget()
        controls_host.setMinimumWidth(210)
        controls_host.setMaximumWidth(260)
        controls = QVBoxLayout(controls_host)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(Spacing.SM)
        mode_title = QLabel(tr("Selection mode"))
        mode_title.setObjectName("CardTitle")
        controls.addWidget(mode_title)

        self.individual = QPushButton(tr("Select individually"))
        self.polygon = QPushButton(tr("Select by polygon"))
        self.individual.setCheckable(True)
        self.polygon.setCheckable(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.individual)
        self.mode_group.addButton(self.polygon)
        controls.addWidget(self.individual)
        controls.addWidget(self.polygon)

        self.finish_polygon = set_button_role(QPushButton(tr("Finish polygon")), "secondary")
        self.finish_polygon.setEnabled(False)
        self.finish_polygon.hide()
        controls.addWidget(self.finish_polygon)

        controls.addSpacing(Spacing.XS)
        fit = set_button_role(QPushButton(tr("Fit view")), "secondary")
        self.clear = set_button_role(QPushButton(tr("Clear selection")), "secondary")
        self.select_all = set_button_role(QPushButton(tr("Select all")), "secondary")
        controls.addWidget(fit)
        controls.addWidget(self.clear)
        controls.addWidget(self.select_all)

        self.count = QLabel()
        self.count.setObjectName("SummaryValue")
        controls.addSpacing(Spacing.SM)
        controls.addWidget(self.count)

        help_text = QLabel(
            tr("Blue: selected. Amber outline: assigned to another group. Selecting an assigned hole moves it to this group when you apply the change.")
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
        apply_button = set_button_role(QPushButton(tr("Apply assignment")), "primary")
        cancel.setAutoDefault(False)
        apply_button.setDefault(True)
        cancel.clicked.connect(self.reject)
        apply_button.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(apply_button)
        layout.addLayout(actions)

        self.individual.clicked.connect(lambda: self._set_mode("individual"))
        self.polygon.clicked.connect(lambda: self._set_mode("polygon"))
        self.finish_polygon.clicked.connect(self.view.complete_polygon)
        fit.clicked.connect(self.view.fit_all)
        self.clear.clicked.connect(self.view.clear_selection)
        self.select_all.clicked.connect(self.view.select_all)
        self.view.selection_changed.connect(self._update_count)
        self.view.polygon_state_changed.connect(self.finish_polygon.setEnabled)
        self._set_mode("individual")
        self._update_count()

    def _set_mode(self, mode: str):
        polygon_mode = mode == "polygon"
        self.individual.setChecked(not polygon_mode)
        self.polygon.setChecked(polygon_mode)
        set_button_role(self.individual, "secondary" if polygon_mode else "primary")
        set_button_role(self.polygon, "primary" if polygon_mode else "secondary")
        self.finish_polygon.setVisible(polygon_mode)
        self.view.set_mode(mode)
        self.instruction.setText(
            tr("Click drillhole collars to add or remove them from this group. Drag to pan and use the mouse wheel to zoom.")
            if not polygon_mode
            else tr("Click at least three vertices around the drillholes, then choose Finish polygon or double-click. Press Esc to cancel the polygon.")
        )
        self.view.setFocus()

    def _update_count(self):
        self.count.setText(
            tr("Selected: %1 / %2")
            .replace("%1", str(len(self.view.selected_ids)))
            .replace("%2", str(len(self.view.holes)))
        )

    @property
    def selected_hole_ids(self) -> set[str]:
        return set(self.view.selected_ids)
