"""Continuous CAD-style Assessment boundary editor."""
from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem, QGraphicsScene,
                              QMessageBox, QVBoxLayout, QWidget)

from app.localization import tr
from application.services.assessment_areas import AssessmentAreaService
from domain.assessment.geometry import (AssessmentBoundary, ProjectLineSpan, SpatialPoint,
    StraightConnector, derive_plan_polygon, extract_project_line_span, snap_to_project_lines)
from domain.geometry.types import PlanPoint
from ui.presentation_labels import domain_message
from ui.widgets.plan_view import PrototypePlanView

PROJECT_LINE_ROLE = 1001
SNAP_MARKER_ROLE = 1002
SNAP_PIXELS = 10.0


class AssessmentGeometryEditorWidget(QWidget):
    area_created = Signal(str); area_revised = Signal(str); workflow_state_changed = Signal(str)
    state_changed = Signal(); state_saved = Signal()

    def __init__(self, state, commit_geometry: Callable[..., object], parent=None, *, read_only=False):
        super().__init__(parent); self.state=state; self._commit_geometry=commit_geometry; self.read_only=read_only
        self.area_service=AssessmentAreaService(state); self.workflow_state="IDLE"; self.selected_area=None; self._editing_area=None
        self._segments=[]; self._first_point=None; self._last_point=None; self._last_anchor=None; self._candidate=None; self._cursor=None
        self._show_project_lines=True; self._show_grid=True
        self.scene=QGraphicsScene(self); self.plan_view=PrototypePlanView(self.scene)
        self.plan_view.scene_clicked.connect(self._drawing_click); self.plan_view.cursor_moved.connect(self._drawing_move)
        self.plan_view.escape_requested.connect(self.cancel_workflow); self.plan_view.workflow_key_requested.connect(self._workflow_key)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.addWidget(self.plan_view); self.draw_geometry()

    def _set_workflow_state(self, value):
        if value != self.workflow_state: self.workflow_state=value; self.workflow_state_changed.emit(value)
    def _ensure_can_edit(self):
        if self.read_only: raise PermissionError("2D Assessment is read-only for the current user")
    def start_new_area(self):
        self._ensure_can_edit()
        if self.state.active_dataset() is None: raise ValueError("Load or select an active Project Lines dataset first")
        self.selected_area=self._editing_area=None; self._reset(); self._set_workflow_state("DRAWING"); self.plan_view.set_polygon_drawing_mode(True); self.draw_geometry()
    def start_edit(self, area_id):
        self._ensure_can_edit(); area=next((a for a in self.state.assessment_areas if a.id==area_id),None)
        if not area or area.is_archived: raise ValueError("Assessment Area is unavailable for editing")
        self.selected_area=None; self._editing_area=area; self._segments=list(area.boundary.segments)
        first=self._segment_points(self._segments[0])[0]
        if (self._segments and isinstance(self._segments[-1],StraightConnector)
                and self._segment_points(self._segments[-1])[-1] == first):
            self._segments.pop()
        last=self._segment_points(self._segments[-1])[-1]
        self._first_point=first; self._last_point=last; self._last_anchor=getattr(self._segments[-1],"end_anchor",None)
        self._set_workflow_state("DRAWING"); self.plan_view.set_polygon_drawing_mode(True); self.draw_geometry()
    def inspect_area(self, area_id):
        """Show a frozen boundary without consuming navigation clicks."""
        area=next((a for a in self.state.assessment_areas if a.id==area_id),None)
        if not area: raise ValueError("Assessment Area is unavailable")
        self.selected_area=area; self._editing_area=None; self._reset()
        self._set_workflow_state("IDLE"); self.plan_view.set_polygon_drawing_mode(False); self.draw_geometry()
    def _reset(self): self._segments=[]; self._first_point=self._last_point=self._last_anchor=self._candidate=self._cursor=None
    def _world_tolerance(self): return SNAP_PIXELS/max(abs(self.plan_view.transform().m11()),1e-9)
    def _snap(self,x,y):
        dataset=self.state.active_dataset()
        return snap_to_project_lines(PlanPoint(x,y),dataset.id,dataset.lines,self._world_tolerance()) if dataset and self._show_project_lines else None
    def _drawing_move(self,x,y):
        if self.workflow_state!="DRAWING": return
        self._cursor=SpatialPoint(x,y); self._candidate=self._snap(x,y); self.draw_geometry()
    def _drawing_click(self,x,y):
        if self.read_only or self.workflow_state!="DRAWING": return
        candidate=self._snap(x,y); point=candidate.anchor.frozen_point_xyz if candidate else SpatialPoint(x,y)
        anchor=candidate.anchor if candidate else None
        if self._first_point is None: self._first_point=self._last_point=point; self._last_anchor=anchor; self.draw_geometry(); return
        segment=None
        if self._last_anchor and anchor and (self._last_anchor.source_dataset_id,self._last_anchor.source_line_id)==(anchor.source_dataset_id,anchor.source_line_id):
            dataset=self.state.active_dataset(); line=next(l for l in dataset.lines if l.source_id==anchor.source_line_id)
            segment=extract_project_line_span(line,self._last_anchor,anchor)
        else: segment=StraightConnector(self._last_point,point,self._last_anchor,anchor)
        self._segments.append(segment); self._last_point=point; self._last_anchor=anchor; self.draw_geometry()
    def undo_vertex(self):
        if self.workflow_state not in {"DRAWING","CLOSED"}: return
        if self.workflow_state=="CLOSED" and self._segments: self._segments.pop(); self._set_workflow_state("DRAWING")
        elif self._segments: self._segments.pop()
        if self._segments:
            self._last_point=self._segment_points(self._segments[-1])[-1]; self._last_anchor=getattr(self._segments[-1],"end_anchor",None)
        else: self._first_point=self._last_point=self._last_anchor=None
        self.draw_geometry()
    def finish_polygon(self):
        self._ensure_can_edit()
        if self.workflow_state!="DRAWING" or self._first_point is None or self._last_point is None: return
        closing=StraightConnector(self._last_point,self._first_point,self._last_anchor,None)
        try: derive_plan_polygon(AssessmentBoundary(tuple(self._segments+[closing])))
        except ValueError as exc: QMessageBox.warning(self,tr("Invalid assessment area"),domain_message(str(exc))); return
        self._segments.append(closing); self._last_point=self._first_point; self._last_anchor=None; self._set_workflow_state("CLOSED"); self.draw_geometry()
    close_boundary=finish_polygon
    def confirm_boundaries(self):
        self._ensure_can_edit()
        if self.workflow_state!="CLOSED": return
        boundary=AssessmentBoundary(tuple(self._segments)); editing_id=self._editing_area.id if self._editing_area else None
        result=self._commit_geometry(assessment_area_id=editing_id,name=self._editing_area.name if self._editing_area else "Assessment Area",
                                     assessment_date=self._editing_area.assessment_date if self._editing_area else date.today(),boundary=boundary)
        self.selected_area=next(a for a in self.state.assessment_areas if a.id==result.area_id); area_id=result.area_id
        self._finish_workflow(); self.state_changed.emit(); self.state_saved.emit(); (self.area_revised if editing_id else self.area_created).emit(area_id)
    def cancel_workflow(self):
        if not self.has_active_workflow(): return False
        self._finish_workflow(); return True
    def _finish_workflow(self): self.plan_view.set_polygon_drawing_mode(False); self._reset(); self._editing_area=None; self._set_workflow_state("IDLE"); self.draw_geometry()
    def has_active_workflow(self): return self.workflow_state!="IDLE"
    def set_project_lines_visible(self,v):
        self._show_project_lines=v
        if not v: self._candidate=None
        self.draw_geometry()
    def set_grid_visible(self,v): self._show_grid=v; self.draw_geometry()
    def fit_to_extent(self): self.plan_view.fit_to_extent()
    def _workflow_key(self,key):
        if key=="back": self.undo_vertex()
        elif key=="enter" and self.workflow_state=="DRAWING": self.finish_polygon()
        elif key=="enter" and self.workflow_state=="CLOSED": self.confirm_boundaries()
    @staticmethod
    def _segment_points(s): return s.frozen_trace_xyz if isinstance(s,ProjectLineSpan) else (s.start_point,s.end_point)
    def draw_geometry(self):
        self.scene.clear(); dataset=self.state.active_dataset()
        if dataset and self._show_project_lines:
            for line in dataset.lines: self._draw_points(line.points,QPen(QColor(125,140,150),1),10)
        if self.selected_area: self._draw_points(self.selected_area.final_geometry_frozen.ring,QPen(QColor(20,110,190),3),20)
        for segment in self._segments:
            self._draw_points(self._segment_points(segment),QPen(QColor(20,125,205) if isinstance(segment,ProjectLineSpan) else QColor(225,125,25),3),50)
        if self._candidate:
            self._draw_snap_marker(self._candidate.anchor.frozen_point_xyz)
        if self._last_point and self._cursor and self.workflow_state=="DRAWING":
            target=self._candidate.anchor.frozen_point_xyz if self._candidate else self._cursor
            if self._last_anchor and self._candidate and self._last_anchor.source_line_id==self._candidate.anchor.source_line_id:
                line=next(l for l in dataset.lines if l.source_id==self._candidate.anchor.source_line_id); preview=extract_project_line_span(line,self._last_anchor,self._candidate.anchor).frozen_trace_xyz; color=QColor(30,175,90)
            else: preview=(self._last_point,target); color=QColor(225,125,25)
            self._draw_points(preview,QPen(color,2,Qt.PenStyle.DashLine),80)
    def _draw_snap_marker(self,point):
        item=QGraphicsEllipseItem(-4,-4,8,8); item.setPos(point.x,-point.y)
        item.setPen(QPen(QColor(20,135,215),1.5)); item.setBrush(QColor(255,255,255,220))
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        item.setZValue(90); item.setData(SNAP_MARKER_ROLE,True); self.scene.addItem(item)
    def _draw_points(self,points,pen,z):
        if len(points)<2:return
        path=QPainterPath(QPointF(points[0].x,-points[0].y))
        for p in points[1:]: path.lineTo(p.x,-p.y)
        item=QGraphicsPathItem(path); item.setPen(pen); item.setZValue(z); item.setData(PROJECT_LINE_ROLE,z==10); self.scene.addItem(item)
