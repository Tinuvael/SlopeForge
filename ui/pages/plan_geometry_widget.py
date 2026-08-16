
from app.localization import tr
"""Reusable plan viewer built on the prototype's established plan view."""
from PySide6.QtCore import QPointF,Signal
from PySide6.QtGui import QBrush,QPainterPath,QPen,QColor
from PySide6.QtWidgets import QCheckBox,QGraphicsScene,QHBoxLayout,QLabel,QPushButton,QVBoxLayout,QWidget
from domain.geometry.types import PlanMultiPoint, PlanPolygon
from ui.widgets.plan_view import PrototypePlanView

class PlanGeometryWidget(QWidget):
    reimport_requested=Signal()
    def __init__(self,parent=None):
        super().__init__(parent); self.scene=QGraphicsScene(self); self.view=PrototypePlanView(self.scene); self._project_items=[]; self.comparison_geometries=(None,None)
        layout=QVBoxLayout(self); bar=QHBoxLayout(); self.context=QLabel(tr("Geometry is not loaded")); self.lines=QCheckBox(tr("Project Lines")); self.lines.setChecked(True); self.lines.toggled.connect(self._toggle_lines); fit=QPushButton(tr("Fit")); fit.clicked.connect(self.fit); self.reimport_button=QPushButton(tr("Reimport geometry")); self.reimport_button.clicked.connect(self.reimport_requested); bar.addWidget(self.context); bar.addStretch(); bar.addWidget(self.lines); bar.addWidget(fit); bar.addWidget(self.reimport_button); layout.addLayout(bar); layout.addWidget(self.view)
    def set_reimport_enabled(self,enabled): self.reimport_button.setEnabled(enabled)
    def set_geometry(self,geometry,project_lines=(),context=""):
        self.scene.clear(); self._project_items=[]; self.comparison_geometries=(None,None); self.context.setText(context or "Plan geometry")
        self._add_project_lines(project_lines); self._add_geometry(geometry,"#1261a0",2); self.fit()
    def set_comparison_geometry(self,primary_geometry,comparison_geometry,project_lines=(),context=""):
        """Render two read-only plan geometries without changing set_geometry callers."""
        self.scene.clear(); self._project_items=[]; self.comparison_geometries=(primary_geometry,comparison_geometry); self.context.setText(context)
        self._add_project_lines(project_lines); self._add_geometry(primary_geometry,"#1261a0",2,QColor(18,97,160,30)); self._add_geometry(comparison_geometry,"#d97706",2,QColor(217,119,6,35)); self.fit()
    def _add_project_lines(self,project_lines):
        pen=QPen(QColor("#8795a1"),0)
        for line in project_lines:
            path=QPainterPath(); points=getattr(line,"points",())
            if not points:continue
            path.moveTo(QPointF(points[0].x,-points[0].y))
            for point in points[1:]:path.lineTo(QPointF(point.x,-point.y))
            item=self.scene.addPath(path,pen); self._project_items.append(item)
    def _add_geometry(self,geometry,color,width,fill=None):
        pen=QPen(QColor(color),width); brush=QBrush(fill) if fill is not None else QBrush()
        if isinstance(geometry,PlanPolygon):
            path=QPainterPath(); ring=geometry.ring
            if ring:
                path.moveTo(QPointF(ring[0].x,-ring[0].y))
                for point in ring[1:]:path.lineTo(QPointF(point.x,-point.y))
                path.closeSubpath(); self.scene.addPath(path,pen,brush)
        elif isinstance(geometry,PlanMultiPoint):
            for point in geometry.points:self.scene.addEllipse(point.x-2,-point.y-2,4,4,pen,brush)
    def _toggle_lines(self,shown):
        for item in self._project_items:item.setVisible(shown)
    def fit(self):
        rect=self.scene.itemsBoundingRect()
        if not rect.isNull():self.view.fitInView(rect, self.view.aspectRatioMode()) if hasattr(self.view,"aspectRatioMode") else self.view.fitInView(rect)
