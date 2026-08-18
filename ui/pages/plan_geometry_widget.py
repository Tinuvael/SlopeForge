"""Reusable, read-only plan viewer with optional comparison and focus extents."""

from app.localization import tr
from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox, QGraphicsScene, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Signal

from domain.geometry.types import PlanMultiPoint, PlanPolygon
from ui.widgets.plan_view import PrototypePlanView


class PlanGeometryWidget(QWidget):
    reimport_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = PrototypePlanView(self.scene)
        self._project_items = []
        self.comparison_geometries = (None, None)
        self.focus_geometry = None
        self.canonical_focus_rect = None
        self._pending_center = False

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.context = QLabel(tr("Geometry is not loaded"))
        self.lines = QCheckBox(tr("Project Lines"))
        self.lines.setChecked(True)
        self.lines.toggled.connect(self._toggle_lines)
        self.frame_button = QPushButton(tr("Fit"))
        self.frame_button.clicked.connect(self.fit)
        self.reimport_button = QPushButton(tr("Reimport geometry"))
        self.reimport_button.clicked.connect(self.reimport_requested)
        bar.addWidget(self.context)
        bar.addStretch()
        bar.addWidget(self.lines)
        bar.addWidget(self.frame_button)
        bar.addWidget(self.reimport_button)
        layout.addLayout(bar)
        layout.addWidget(self.view)

    def set_reimport_enabled(self, enabled):
        self.reimport_button.setEnabled(enabled)

    def use_center_control(self, enabled=True):
        """Make the framing action restore a focus geometry instead of fitting all."""
        self.frame_button.setText(tr("Center") if enabled else tr("Fit"))
        try:
            self.frame_button.clicked.disconnect()
        except RuntimeError:
            pass
        self.frame_button.clicked.connect(self.center_on_focus if enabled else self.fit)

    def set_context_visible(self, visible):
        self.context.setVisible(visible)

    def set_context(self, context):
        self.context.setText(context)

    def set_geometry(self, geometry, project_lines=(), context="", *, focus_geometry=None):
        self.scene.clear()
        self._project_items = []
        self.comparison_geometries = (None, None)
        self.context.setText(context or "Plan geometry")
        self._add_project_lines(project_lines)
        self._add_geometry(geometry, "#1261a0", 2)
        self.focus_geometry = focus_geometry
        if focus_geometry is None:
            self.canonical_focus_rect = None
            self._pending_center = False
            self.fit()
        else:
            self._update_focus_rect()
            self.center_on_focus()

    def set_comparison_geometry(self, primary_geometry, comparison_geometry,
                                project_lines=(), context="", *, focus_geometry=None,
                                recenter=False):
        """Update overlays while retaining the user's camera unless recenter is requested."""
        transform = self.view.transform()
        center = self.view.mapToScene(self.view.viewport().rect().center())
        self.scene.clear()
        self._project_items = []
        self.comparison_geometries = (primary_geometry, comparison_geometry)
        if context:
            self.context.setText(context)
        self._add_project_lines(project_lines)
        self._add_geometry(primary_geometry, "#1261a0", 2, QColor(18, 97, 160, 25))
        self._add_geometry(comparison_geometry, "#d97706", 2, QColor(217, 119, 6, 38))
        if focus_geometry is not None:
            self.focus_geometry = focus_geometry
            self._update_focus_rect()
        if recenter:
            self.center_on_focus()
        else:
            self.view.setTransform(transform)
            self.view.centerOn(center)

    def _update_focus_rect(self):
        rect = self._geometry_path(self.focus_geometry).boundingRect()
        if rect.isNull():
            self.canonical_focus_rect = None
            self._pending_center = False
            return
        # Overview framing contract: the focused entity occupies roughly half of
        # the viewport span, leaving project-line and neighbouring geometry context.
        factor = 2.0
        width, height = rect.width() * factor, rect.height() * factor
        center = rect.center()
        self.canonical_focus_rect = rect.__class__(
            center.x() - width / 2, center.y() - height / 2, width, height,
        )

    def center_on_focus(self):
        if self.canonical_focus_rect is None:
            return
        viewport = self.view.viewport()
        if not self.isVisible() or viewport.width() < 2 or viewport.height() < 2:
            self._pending_center = True
            return
        self.view.fit_to_rect(self.canonical_focus_rect)
        self._pending_center = False

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending_center:
            # A hidden tab has only provisional viewport dimensions. Defer the
            # canonical framing until Qt has completed the visible layout pass.
            QTimer.singleShot(0, self.center_on_focus)

    def _add_project_lines(self, project_lines):
        pen = QPen(QColor("#aeb7c2"), 0)
        for line in project_lines:
            points = getattr(line, "points", ())
            if not points:
                continue
            path = QPainterPath()
            path.moveTo(QPointF(points[0].x, -points[0].y))
            for point in points[1:]:
                path.lineTo(QPointF(point.x, -point.y))
            self._project_items.append(self.scene.addPath(path, pen))

    @staticmethod
    def _geometry_path(geometry):
        path = QPainterPath()
        if isinstance(geometry, PlanPolygon) and geometry.ring:
            path.moveTo(QPointF(geometry.ring[0].x, -geometry.ring[0].y))
            for point in geometry.ring[1:]:
                path.lineTo(QPointF(point.x, -point.y))
            path.closeSubpath()
        elif isinstance(geometry, PlanMultiPoint):
            for point in geometry.points:
                path.addEllipse(point.x - 2, -point.y - 2, 4, 4)
        return path

    def _add_geometry(self, geometry, color, width, fill=None):
        path = self._geometry_path(geometry)
        if not path.isEmpty():
            brush = QBrush(fill) if fill is not None else QBrush()
            self.scene.addPath(path, QPen(QColor(color), width), brush)

    def _toggle_lines(self, shown):
        for item in self._project_items:
            item.setVisible(shown)

    def fit(self):
        self.view.fit_to_extent()
