
from app.localization import tr
"""Reusable plan viewer built on the prototype's established plan view."""
from PySide6.QtCore import QPointF,Signal
from PySide6.QtGui import QPainterPath,QPen,QColor
from PySide6.QtWidgets import QCheckBox,QGraphicsScene,QHBoxLayout,QLabel,QPushButton,QVBoxLayout,QWidget
from prototype_2d.domain import PlanMultiPoint,PlanPolygon
from ui.widgets.plan_view import PrototypePlanView

class PlanGeometryWidget(QWidget):
    reimport_requested=Signal()
    def __init__(self,parent=None):
        super().__init__(parent); self.scene=QGraphicsScene(self); self.view=PrototypePlanView(self.scene); self._project_items=[]
        layout=QVBoxLayout(self); bar=QHBoxLayout(); self.context=QLabel(tr("Geometry is not loaded")); self.lines=QCheckBox(tr("Project Lines")); self.lines.setChecked(True); self.lines.toggled.connect(self._toggle_lines); fit=QPushButton(tr("Fit")); fit.clicked.connect(self.fit); self.reimport_button=QPushButton(tr("Reimport geometry")); self.reimport_button.clicked.connect(self.reimport_requested); bar.addWidget(self.context); bar.addStretch(); bar.addWidget(self.lines); bar.addWidget(fit); bar.addWidget(self.reimport_button); layout.addLayout(bar); layout.addWidget(self.view)
    def set_reimport_enabled(self,enabled): self.reimport_button.setEnabled(enabled)
    def set_geometry(self,geometry,project_lines=(),context=""):
        self.scene.clear(); self._project_items=[]; self.context.setText(context or "Plan geometry")
        pen=QPen(QColor("#8795a1"),0)
        for line in project_lines:
            path=QPainterPath(); points=getattr(line,"points",())
            if not points:continue
            path.moveTo(QPointF(points[0].x,-points[0].y))
            for point in points[1:]:path.lineTo(QPointF(point.x,-point.y))
            item=self.scene.addPath(path,pen); self._project_items.append(item)
        if isinstance(geometry,PlanPolygon):
            path=QPainterPath(); ring=geometry.ring
            if ring:
                path.moveTo(QPointF(ring[0].x,-ring[0].y))
                for point in ring[1:]:path.lineTo(QPointF(point.x,-point.y))
                path.closeSubpath(); self.scene.addPath(path,QPen(QColor("#1261a0"),2))
        elif isinstance(geometry,PlanMultiPoint):
            for point in geometry.points:self.scene.addEllipse(point.x-2,-point.y-2,4,4,QPen(QColor("#1261a0"),2))
        self.fit()
    def _toggle_lines(self,shown):
        for item in self._project_items:item.setVisible(shown)
    def fit(self):
        rect=self.scene.itemsBoundingRect()
        if not rect.isNull():self.view.fitInView(rect, self.view.aspectRatioMode()) if hasattr(self.view,"aspectRatioMode") else self.view.fitInView(rect)
