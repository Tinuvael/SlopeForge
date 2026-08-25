"""Compact modal editor for a Domain's detached multi-polygon working copy."""
from app.localization import tr
from PySide6.QtCore import Qt, QLineF, QRectF
from PySide6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QGraphicsEllipseItem, QGraphicsPathItem,
    QGraphicsScene, QGraphicsView, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.geometry.operations import validate_simple_polygon
from ui.presentation_labels import domain_message
from ui.theme import Spacing
from ui.widgets.design_system import set_button_role


class _DrawingView(QGraphicsView):
    GRID_SPACING = 50.0

    def __init__(self, scene, owner):
        super().__init__(scene)
        self.owner = owner

    def mousePressEvent(self, event):
        if self.owner.drawing and event.button() == Qt.MouseButton.LeftButton:
            point = self.mapToScene(event.position().toPoint())
            self.owner.add_vertex(point.x(), -point.y())
            return
        super().mousePressEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        palette = self.palette()
        painter.fillRect(rect, palette.color(QPalette.ColorRole.AlternateBase))
        if not self.owner.grid_toggle.isChecked():
            return
        spacing = self.GRID_SPACING
        left = int(rect.left() // spacing) * spacing
        top = int(rect.top() // spacing) * spacing
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Dark), 0))
        x = left
        while x <= rect.right():
            painter.drawLine(QLineF(x, rect.top(), x, rect.bottom())); x += spacing
        y = top
        while y <= rect.bottom():
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y)); y += spacing


class DomainGeometryEditorDialog(QDialog):
    """Edits a working copy. Callers persist only after ``Accepted``."""

    def __init__(self, polygons=(), project_lines=(), parent=None):
        super().__init__(parent)
        self.setObjectName("DomainGeometryEditor")
        self.setWindowTitle(tr("Domain geometry"))
        self.resize(1200, 780)
        self.setMinimumSize(900, 620)
        self.polygons = list(polygons)
        self.project_lines = project_lines
        self.drawing = False
        self.vertices = []
        self.selected_index = None
        self.handles = []

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        root.setSpacing(Spacing.MD)
        title = QLabel(tr("Domain geometry")); title.setObjectName("EntityTitle")
        subtitle = QLabel(tr("Draw or edit one or more polygons for this Domain."))
        subtitle.setObjectName("MutedText")
        root.addWidget(title); root.addWidget(subtitle)

        body = QHBoxLayout(); body.setSpacing(Spacing.MD)
        plan = QFrame(); plan.setObjectName("PlanCard")
        plan.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plan_layout = QVBoxLayout(plan)
        plan_layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.MD)
        plan_layout.setSpacing(Spacing.SM)
        toolbar = QHBoxLayout(); toolbar.setSpacing(Spacing.SM)
        plan_title = QLabel(tr("Plan")); plan_title.setObjectName("CardTitle")
        toolbar.addWidget(plan_title); toolbar.addStretch(1)
        self.lines_toggle = QCheckBox(tr("Project Lines")); self.lines_toggle.setChecked(True)
        self.grid_toggle = QCheckBox(tr("Grid")); self.grid_toggle.setChecked(True)
        self.fit_button = set_button_role(QPushButton(tr("Fit")), "link")
        self.add_button = set_button_role(QPushButton(tr("Add polygon")), "secondary")
        self.undo_button = set_button_role(QPushButton(tr("Undo vertex")), "link")
        self.finish_button = set_button_role(QPushButton(tr("Finish polygon")), "primary")
        self.delete_button = set_button_role(QPushButton(tr("Delete polygon")), "danger")
        for widget in (self.lines_toggle, self.grid_toggle, self.fit_button, self.add_button,
                       self.undo_button, self.finish_button, self.delete_button):
            toolbar.addWidget(widget)
        plan_layout.addLayout(toolbar)
        self.scene = QGraphicsScene(self)
        self.view = _DrawingView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        plan_layout.addWidget(self.view, 1)
        body.addWidget(plan, 3)

        inspector = QFrame(); inspector.setObjectName("InspectorCard")
        inspector.setMinimumWidth(220); inspector.setMaximumWidth(300)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(Spacing.CARD_HORIZONTAL, Spacing.CARD_VERTICAL,
                                            Spacing.CARD_HORIZONTAL, Spacing.CARD_VERTICAL)
        inspector_layout.setSpacing(Spacing.SM)
        heading = QLabel(tr("Geometry")); heading.setObjectName("CardTitle")
        inspector_layout.addWidget(heading)
        summary = QGridLayout(); summary.setHorizontalSpacing(Spacing.SM); summary.setVerticalSpacing(Spacing.SM)
        self.polygons_value = QLabel(); self.selected_value = QLabel(); self.mode_value = QLabel()
        for row, (name, value) in enumerate((("Polygons", self.polygons_value),
                                              ("Selected", self.selected_value), ("Mode", self.mode_value))):
            label = QLabel(tr(name)); label.setObjectName("MutedText")
            value.setObjectName("InspectorValue")
            summary.addWidget(label, row, 0); summary.addWidget(value, row, 1)
        inspector_layout.addLayout(summary)
        section = QLabel(tr("How to edit")); section.setObjectName("SectionTitle")
        inspector_layout.addWidget(section)
        self.help_labels = [QLabel() for _ in range(3)]
        for label in self.help_labels:
            label.setWordWrap(True); inspector_layout.addWidget(label)
        inspector_layout.addStretch(1)
        body.addWidget(inspector, 1)
        root.addLayout(body, 1)

        footer = QFrame(); footer.setObjectName("DialogFooter")
        actions = QHBoxLayout(footer); actions.setContentsMargins(Spacing.MD, 7, Spacing.MD, 7)
        self.status_label = QLabel(); self.status_label.setObjectName("DialogStatus")
        actions.addWidget(self.status_label); actions.addStretch(1)
        self.cancel_button = set_button_role(QPushButton(tr("Cancel")), "secondary")
        self.save_button = set_button_role(QPushButton(tr("Save")), "primary")
        for button in (self.cancel_button, self.save_button):
            button.setMinimumWidth(96); button.setFixedHeight(32)
        self.save_button.setDefault(True)
        actions.addWidget(self.cancel_button); actions.addWidget(self.save_button)
        root.addWidget(footer)

        self.fit_button.clicked.connect(self.fit)
        self.lines_toggle.toggled.connect(self._rerender_preserving_edits)
        self.grid_toggle.toggled.connect(self._rerender_preserving_edits)
        self.add_button.clicked.connect(self.start_polygon)
        self.undo_button.clicked.connect(self.undo_vertex)
        self.finish_button.clicked.connect(self.finish_polygon)
        self.delete_button.clicked.connect(self.delete_selected)
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(self.reject)
        self.render(preserve_view=False); self.fit()

    def _warning(self, message):
        QMessageBox.warning(self, tr("Domain geometry"), domain_message(str(message)))

    def _rerender_preserving_edits(self, *_):
        self._sync_handles(); self.render()

    def _set_drawing_mode(self, active):
        self.drawing = active
        if active:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.viewport().unsetCursor()
        self._sync_presentation()

    def _sync_presentation(self):
        self.polygons_value.setText(str(len(self.polygons)))
        self.selected_value.setText(tr("polygon %1").replace("%1", str(self.selected_index + 1))
                                    if self.selected_index is not None else "—")
        self.mode_value.setText(tr("Drawing") if self.drawing else tr("Explore"))
        normal_help = ("Select a polygon to edit its vertices.",
                       "Drag vertex handles to adjust geometry.",
                       "Use Add polygon to create another boundary.")
        drawing_help = ("Click the plan to add vertices.", "Undo removes the last vertex.",
                        "Finish closes and validates the polygon.")
        for label, text in zip(self.help_labels, drawing_help if self.drawing else normal_help):
            label.setText(tr(text))
        self.add_button.setVisible(not self.drawing)
        self.delete_button.setVisible(not self.drawing and self.selected_index is not None)
        self.undo_button.setVisible(self.drawing)
        self.finish_button.setVisible(self.drawing)
        self.undo_button.setEnabled(self.drawing and bool(self.vertices))
        self.finish_button.setEnabled(self.drawing)
        self.status_label.setText(
            tr("Click the plan to add vertices.") if self.drawing
            else tr("Select a polygon or add a new one. Wheel to zoom · drag to pan."))

    def start_polygon(self):
        self._sync_handles(); self._set_drawing_mode(True)
        self.vertices = []; self.selected_index = None; self.render()

    def add_vertex(self, x, y):
        self.vertices.append(PlanPoint(x, y)); self.render()

    def undo_vertex(self):
        if self.drawing and self.vertices:
            self.vertices.pop(); self.render()

    def finish_polygon(self):
        if len(self.vertices) < 3:
            self._warning(tr("A polygon requires at least three vertices.")); return
        polygon = PlanPolygon(tuple(self.vertices + [self.vertices[0]]))
        try:
            validate_simple_polygon(polygon)
        except ValueError as exc:
            self._warning(exc); return
        self.polygons.append(polygon); self.selected_index = len(self.polygons) - 1
        self.vertices = []; self._set_drawing_mode(False); self.render()

    def reject(self):
        self._set_drawing_mode(False); super().reject()

    def delete_selected(self):
        self._sync_handles()
        if self.selected_index is not None:
            self.polygons.pop(self.selected_index); self.selected_index = None; self.render()

    def _select(self, index):
        self._sync_handles(); self.selected_index = index; self.render()

    def _sync_handles(self):
        if self.selected_index is None or not self.handles:
            return
        ring = tuple(PlanPoint(handle.scenePos().x(), -handle.scenePos().y()) for handle in self.handles)
        if len(ring) >= 3:
            self.polygons[self.selected_index] = PlanPolygon(ring + (ring[0],))

    def save(self):
        self._sync_handles()
        if not self.polygons:
            self._warning(tr("At least one polygon is required.")); return
        try:
            for polygon in self.polygons:
                validate_simple_polygon(polygon)
        except ValueError as exc:
            self._warning(exc); return
        self.accept()

    def render(self, preserve_view=True):
        transform = self.view.transform() if preserve_view else None
        center = self.view.mapToScene(self.view.viewport().rect().center()) if preserve_view else None
        self.scene.clear(); self.handles = []; self._line_items = []
        if self.lines_toggle.isChecked():
            for geometry in self.project_lines:
                item = self._path(geometry.points, "#94A3B8", 1, None, -10, cosmetic=True, opacity=0.45)
                self._line_items.append(item)
        for index, polygon in enumerate(self.polygons):
            item = self._path(tuple((point.x, point.y) for point in polygon.ring), "#0F766E",
                              2 if index == self.selected_index else 1.3, "#99F6E4", 0)
            item.mousePressEvent = lambda event, i=index: self._select(i)
        if self.selected_index is not None:
            for point in self.polygons[self.selected_index].ring[:-1]:
                handle = QGraphicsEllipseItem(-4, -4, 8, 8); handle.setPos(point.x, -point.y)
                handle.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable)
                handle.setBrush(QColor("#0F766E")); handle.setZValue(10)
                self.scene.addItem(handle); self.handles.append(handle)
        if self.vertices:
            self._path(tuple((point.x, point.y) for point in self.vertices), "#2563EB", 2, None, 5)
        if preserve_view:
            self.view.setTransform(transform); self.view.centerOn(center)
        self.view.viewport().update(); self._sync_presentation()

    def _path(self, points, color, width, fill, z, cosmetic=False, opacity=1.0):
        path = QPainterPath(); x, y = points[0]; path.moveTo(x, -y)
        for x, y in points[1:]:
            path.lineTo(x, -y)
        item = QGraphicsPathItem(path); pen = QPen(QColor(color), width); pen.setCosmetic(cosmetic)
        item.setPen(pen)
        if fill:
            fill_color = QColor(fill); fill_color.setAlpha(50); item.setBrush(QBrush(fill_color))
        else:
            item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        item.setOpacity(opacity); item.setZValue(z); self.scene.addItem(item); return item

    def fit(self):
        rect = self.scene.itemsBoundingRect()
        if not rect.isNull():
            self.view.fitInView(rect.adjusted(-10, -10, 10, 10), Qt.AspectRatioMode.KeepAspectRatio)
