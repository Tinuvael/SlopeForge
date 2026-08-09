"""Small modal multi-polygon editor for a Domain's current XY footprint."""
from app.localization import tr
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox,QDialog,QGraphicsEllipseItem,QGraphicsPathItem,
 QGraphicsScene,QGraphicsView,QHBoxLayout,QMessageBox,QPushButton,QVBoxLayout)
from prototype_2d.domain import PlanPoint,PlanPolygon

class _DrawingView(QGraphicsView):
    def __init__(self,scene,owner): super().__init__(scene); self.owner=owner
    def mousePressEvent(self,event):
        if self.owner.drawing and event.button()==Qt.MouseButton.LeftButton:
            p=self.mapToScene(event.position().toPoint()); self.owner.add_vertex(p.x(),-p.y()); return
        super().mousePressEvent(event)

class DomainGeometryEditorDialog(QDialog):
    """Edits a detached working copy; persistence happens only after Save."""
    def __init__(self,polygons=(),project_lines=(),parent=None):
        super().__init__(parent); self.setWindowTitle(tr("Domain geometry editor")); self.resize(1200,780)
        self.polygons=list(polygons); self.project_lines=project_lines; self.drawing=False; self.vertices=[]; self.selected_index=None; self.handles=[]
        root=QVBoxLayout(self); controls=QHBoxLayout()
        self.fit_button=QPushButton(tr("Fit")); self.lines_toggle=QCheckBox(tr("Project Lines")); self.lines_toggle.setChecked(True); self.grid_toggle=QCheckBox(tr("Grid")); self.grid_toggle.setChecked(True)
        self.add_button=QPushButton(tr("Add polygon")); self.undo_button=QPushButton(tr("Undo vertex")); self.finish_button=QPushButton(tr("Finish polygon")); self.delete_button=QPushButton(tr("Delete selected polygon"))
        for w in (self.fit_button,self.lines_toggle,self.grid_toggle,self.add_button,self.undo_button,self.finish_button,self.delete_button): controls.addWidget(w)
        controls.addStretch(); root.addLayout(controls); self.scene=QGraphicsScene(self); self.view=_DrawingView(self.scene,self); self.view.setRenderHint(QPainter.RenderHint.Antialiasing); self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); root.addWidget(self.view)
        actions=QHBoxLayout(); actions.addStretch(); save=QPushButton(tr("Save")); cancel=QPushButton(tr("Cancel")); actions.addWidget(save); actions.addWidget(cancel); root.addLayout(actions)
        self.fit_button.clicked.connect(self.fit); self.lines_toggle.toggled.connect(self.render); self.grid_toggle.toggled.connect(self.render); self.add_button.clicked.connect(self.start_polygon); self.undo_button.clicked.connect(self.undo_vertex); self.finish_button.clicked.connect(self.finish_polygon); self.delete_button.clicked.connect(self.delete_selected); save.clicked.connect(self.save); cancel.clicked.connect(self.reject); self.render()
    def start_polygon(self): self.drawing=True; self.vertices=[]; self.selected_index=None; self.render()
    def add_vertex(self,x,y): self.vertices.append(PlanPoint(x,y)); self.render()
    def undo_vertex(self):
        if self.drawing and self.vertices:self.vertices.pop(); self.render()
    def finish_polygon(self):
        if len(self.vertices)<3: QMessageBox.warning(self,tr("Domain geometry"),tr("A polygon requires at least three vertices.")); return
        self.polygons.append(PlanPolygon(tuple(self.vertices+[self.vertices[0]]))); self.selected_index=len(self.polygons)-1; self.vertices=[]; self.drawing=False; self.render()
    def delete_selected(self):
        if self.selected_index is not None: self.polygons.pop(self.selected_index); self.selected_index=None; self.render()
    def _select(self,index): self.selected_index=index; self.render()
    def _sync_handles(self):
        if self.selected_index is None:return
        ring=[]
        for h in self.handles:ring.append(PlanPoint(h.scenePos().x(),-h.scenePos().y()))
        if len(ring)>=3:self.polygons[self.selected_index]=PlanPolygon(tuple(ring+[ring[0]]))
    def save(self):
        self._sync_handles()
        if not self.polygons: QMessageBox.warning(self,tr("Domain geometry"),tr("At least one polygon is required.")); return
        self.accept()
    def render(self):
        self.scene.clear(); self.handles=[]
        if self.grid_toggle.isChecked(): self.scene.setBackgroundBrush(QBrush(QColor("#F8FAFC")))
        self._line_items=[]
        if self.lines_toggle.isChecked():
            for geometry in self.project_lines:self._path(geometry.points,"#CBD5E1",1,None,-10)
        for index,polygon in enumerate(self.polygons):
            item=self._path(tuple((p.x,p.y) for p in polygon.ring),"#0F766E",2 if index==self.selected_index else 1.3,"#99F6E4",0); item.mousePressEvent=lambda event,i=index:self._select(i)
        if self.selected_index is not None:
            for p in self.polygons[self.selected_index].ring[:-1]:
                h=QGraphicsEllipseItem(-4,-4,8,8); h.setPos(p.x,-p.y); h.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable); h.setBrush(QColor("#0F766E")); h.setZValue(10); self.scene.addItem(h); self.handles.append(h)
        if self.vertices:self._path(tuple((p.x,p.y) for p in self.vertices),"#2563EB",2,None,5)
        self.fit()
    def _path(self,points,color,width,fill,z):
        path=QPainterPath(); x,y=points[0]; path.moveTo(x,-y)
        for x,y in points[1:]:path.lineTo(x,-y)
        item=QGraphicsPathItem(path); item.setPen(QPen(QColor(color),width)); fc=QColor(fill) if fill else QColor(Qt.GlobalColor.transparent); fc.setAlpha(50); item.setBrush(fc); item.setZValue(z); self.scene.addItem(item); return item
    def fit(self):
        rect=self.scene.itemsBoundingRect()
        if not rect.isNull():self.view.fitInView(rect.adjusted(-10,-10,10,10),Qt.AspectRatioMode.KeepAspectRatio)
