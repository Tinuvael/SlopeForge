
from app.localization import tr
"""Isolated read-only Domain plan projection."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QCheckBox,QGraphicsEllipseItem,QGraphicsPathItem,QGraphicsScene,QGraphicsView,QHBoxLayout,QLabel,QPushButton,QVBoxLayout,QWidget
from app.icons.ui.ui_icons import ui_icon
from .widgets import quadrant_presentation

class DashboardPlanOverviewWidget(QWidget):
    def __init__(self,snapshot):
        super().__init__(); self.snapshot=snapshot; box=QVBoxLayout(self); controls=QHBoxLayout()
        self.fit_button=QPushButton(tr("Fit")); self.fit_button.setIcon(ui_icon("fit-view")); controls.addWidget(self.fit_button)
        self.project_lines_checkbox=QCheckBox(tr("Project Lines")); self.project_lines_checkbox.setChecked(True); controls.addWidget(self.project_lines_checkbox); controls.addStretch(); box.addLayout(controls)
        self.scene=QGraphicsScene(self); self.view=QGraphicsView(self.scene); self.view.setRenderHint(QPainter.RenderHint.Antialiasing); self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.view.setMinimumHeight(220); self.view.setStyleSheet("border:1px solid #E2E8F0;background:#F8FAFC"); box.addWidget(self.view)
        self.empty_label=QLabel(tr("No plan geometry yet"),self.view.viewport()); self.empty_label.setStyleSheet("color:#64748B;background:transparent"); self.empty_label.hide()
        self._project_items=[]; self._render(); self.fit_button.clicked.connect(self.fit); self.project_lines_checkbox.toggled.connect(self._toggle_project_lines)
    @staticmethod
    def _path(points,close=False):
        path=QPainterPath(); path.moveTo(points[0][0],-points[0][1])
        for x,y in points[1:]: path.lineTo(x,-y)
        if close:path.closeSubpath()
        return path
    def _add_path(self,geometry,color,width=1.5,fill=None,project=False):
        item=QGraphicsPathItem(self._path(geometry.points,close=len(geometry.points)>2)); item.setPen(QPen(QColor(color),width))
        fill_color=QColor(fill) if fill else None
        if fill_color: fill_color.setAlpha(48)
        item.setBrush(QBrush(fill_color) if fill_color else QBrush(Qt.BrushStyle.NoBrush)); self.scene.addItem(item)
        if project:self._project_items.append(item)
    def _render(self):
        for geometry in self.snapshot.project_lines:self._add_path(geometry,"#CBD5E1",1,project=True)
        for geometry in self.snapshot.production_geometries:self._add_path(geometry,"#2563EB",2,"#2563EB")
        for geometry in self.snapshot.contour_geometries:
            for x,y in geometry.points:
                item=QGraphicsEllipseItem(x-2.5,-y-2.5,5,5); item.setPen(QPen(QColor("#0891B2"),1)); item.setBrush(QColor("#06B6D4")); self.scene.addItem(item)
        for geometry in self.snapshot.assessment_geometries:
            color=quadrant_presentation(geometry.quadrant).color if geometry.quadrant else "#64748B"; self._add_path(geometry,color,2,color)
        self.empty_label.setVisible(not bool(self.scene.items())); self.empty_label.adjustSize(); self.empty_label.move(16,16); self.fit()
    def _toggle_project_lines(self,visible):
        for item in self._project_items:item.setVisible(visible)
        self.fit()
    def fit(self):
        rect=self.scene.itemsBoundingRect()
        if not rect.isNull():self.view.fitInView(rect.adjusted(-5,-5,5,5),Qt.AspectRatioMode.KeepAspectRatio)
