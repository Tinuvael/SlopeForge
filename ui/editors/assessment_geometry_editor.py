from copy import deepcopy
from collections.abc import Callable

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsScene, QMessageBox, QVBoxLayout, QWidget,
)

from app.localization import tr
from prototype_2d.assessment_area_service import AssessmentAreaService
from prototype_2d.assessment_event_link_service import AssessmentEventLinkService
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.geometry.operations import validate_simple_polygon
from ui.dialogs.assessment_candidate_dialog import AssessmentCandidateDialog
from ui.presentation_labels import domain_message
from ui.widgets.plan_view import PrototypePlanView

PROJECT_LINE_ROLE = 1001
ASSESSMENT_SELECTION_ROLE = 1003
ASSESSMENT_HANDLE_ROLE = 1004


class PolygonVertexHandle(QGraphicsEllipseItem):
    def __init__(self, index, point, moved, released):
        super().__init__(-6, -6, 12, 12)
        self.index, self._moved, self._released = index, moved, released
        self.setPos(point.x, -point.y)
        self.setBrush(QColor(255, 210, 0)); self.setPen(QPen(QColor(20, 80, 130), 2))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
                      QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setData(ASSESSMENT_HANDLE_ROLE, True); self.setZValue(90)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._moved(self.index, value.x(), -value.y())
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event); self._released(self.index)


class AssessmentGeometryEditorWidget(QWidget):
    """Focused plan editor for creating and revising Assessment Area geometry."""

    area_created = Signal(str)
    area_revised = Signal(str)
    workflow_state_changed = Signal(str)
    state_changed = Signal()
    state_saved = Signal()

    def __init__(self, state, save_callback: Callable[[], None], parent=None, *, read_only=False):
        super().__init__(parent)
        self.state = state
        self._save_callback = save_callback
        self.read_only = read_only
        self.area_service = AssessmentAreaService(state)
        self.link_service = AssessmentEventLinkService(state)
        self.workflow_state = "IDLE"
        self.selected_area = None
        self._editing_area = None
        self._drawing_vertices = []
        self._drawing_cursor = None
        self._candidate_preview = []
        self._refinement_path_item = None
        self._vertex_handles = []
        self._show_project_lines = True
        self._show_grid = True
        self.scene = QGraphicsScene(self)
        self.plan_view = PrototypePlanView(self.scene)
        self.plan_view.scene_clicked.connect(self._drawing_click)
        self.plan_view.scene_double_clicked.connect(lambda _x, _y: self.finish_polygon())
        self.plan_view.cursor_moved.connect(self._drawing_move)
        self.plan_view.escape_requested.connect(self.cancel_workflow)
        self.plan_view.workflow_key_requested.connect(self._workflow_key)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plan_view)
        self.draw_geometry()

    def _ensure_can_edit(self):
        if self.read_only:
            raise PermissionError("2D Assessment is read-only for the current user")

    def _set_workflow_state(self, state):
        if self.workflow_state != state:
            self.workflow_state = state
            self.workflow_state_changed.emit(state)

    def start_new_area(self):
        self._ensure_can_edit()
        if self.state.active_dataset() is None:
            raise ValueError("Load or select an active dataset first")
        self.selected_area = None; self._editing_area = None
        self._drawing_vertices = []; self._drawing_cursor = None; self._candidate_preview = []
        self._set_workflow_state("DRAWING")
        self.plan_view.set_polygon_drawing_mode(True); self.draw_geometry()

    def start_edit(self, area_id):
        self._ensure_can_edit()
        area = next((item for item in self.state.assessment_areas if item.id == area_id), None)
        if area is None:
            raise ValueError("Assessment Area is not available")
        if area.is_archived:
            raise ValueError("Archived Assessment Area is read-only")
        self.selected_area = area; self._editing_area = area
        self._drawing_vertices = list(area.selection_polygon_frozen.ring[:-1])
        self._drawing_cursor = None
        self._set_workflow_state("REFINING")
        self.plan_view.set_polygon_refinement_mode()
        self._refresh_refinement_candidates(); self.draw_geometry()

    def undo_vertex(self):
        if self.workflow_state == "DRAWING" and self._drawing_vertices:
            self._drawing_vertices.pop(); self.draw_geometry()

    def finish_polygon(self):
        self._ensure_can_edit()
        if self.workflow_state != "DRAWING":
            return
        try:
            polygon = self._current_draft_polygon(); validate_simple_polygon(polygon)
        except (ValueError, IndexError) as exc:
            QMessageBox.warning(self, tr("Invalid assessment area"), domain_message(str(exc))); return
        self._drawing_cursor = None; self._set_workflow_state("REFINING")
        self.plan_view.set_polygon_refinement_mode()
        self._refresh_refinement_candidates(); self.draw_geometry()

    def confirm_boundaries(self):
        self._ensure_can_edit()
        if self.workflow_state != "REFINING":
            return
        try:
            polygon = self._current_draft_polygon(); validate_simple_polygon(polygon)
            candidates = self.area_service.generate_candidates(polygon)
            if not candidates:
                raise ValueError("No suitable horizontal lines are inside the polygon")
        except (ValueError, IndexError) as exc:
            QMessageBox.warning(self, tr("Invalid assessment area"), domain_message(str(exc))); return
        self._set_workflow_state("CANDIDATE_CONFIRMATION")
        dialog = AssessmentCandidateDialog(candidates, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_workflow_state("REFINING"); self._refresh_refinement_candidates(); self.draw_geometry(); return

        state_before = deepcopy(self.state)
        editing_id = self._editing_area.id if self._editing_area else None
        try:
            if self._editing_area:
                area = self._editing_area
                self.area_service.revise_area(area, selection_polygon=polygon,
                                              selected_fragments=dialog.selected_candidates())
            else:
                area = self.area_service.create_area(
                    name=dialog.area_name.text(), assessment_date=dialog.area_date.date().toPython(),
                    selection_polygon=polygon, selected_fragments=dialog.selected_candidates())
            try:
                scan = self.link_service.refresh_suggestions(area)
                scan_text = (f"Production: {scan.production_candidates}; Contour: {scan.contour_candidates}; "
                             f"suggestions: {scan.suggestions_added}")
            except Exception as exc:
                scan_text = f"Revision saved, but linked-event search failed: {domain_message(str(exc))}"
            self._save_callback()
        except Exception:
            self._restore_state(state_before)
            self.selected_area = next((item for item in self.state.assessment_areas if item.id == editing_id), None)
            self._editing_area = self.selected_area
            self._set_workflow_state("REFINING")
            self._refresh_refinement_candidates(); self.draw_geometry()
            raise

        area_id = area.id
        self.selected_area = area
        self._finish_workflow()
        self.state_changed.emit(); self.state_saved.emit()
        QMessageBox.information(self, tr("Linked-event search"), scan_text)
        (self.area_revised if editing_id else self.area_created).emit(area_id)

    def _restore_state(self, snapshot):
        for name in ("datasets", "blast_events", "assessment_areas", "technical_cards", "evaluations", "attachments"):
            getattr(self.state, name)[:] = getattr(snapshot, name)
        self.area_service = AssessmentAreaService(self.state)
        self.link_service = AssessmentEventLinkService(self.state)

    def cancel_workflow(self):
        if not self.has_active_workflow():
            return False
        self._finish_workflow(); return True

    def _finish_workflow(self):
        self.plan_view.set_polygon_drawing_mode(False)
        self._drawing_vertices = []; self._drawing_cursor = None; self._candidate_preview = []
        self._editing_area = None; self._set_workflow_state("IDLE"); self.draw_geometry()

    def has_active_workflow(self):
        return self.workflow_state != "IDLE"

    def set_project_lines_visible(self, shown):
        self._show_project_lines = shown; self.draw_geometry()

    def set_grid_visible(self, shown):
        self._show_grid = shown; self.draw_geometry()

    def fit_to_extent(self):
        self.plan_view.fit_to_extent()

    def _workflow_key(self, key):
        if key == "back": self.undo_vertex()
        elif key == "enter" and self.workflow_state == "DRAWING": self.finish_polygon()
        elif key == "enter" and self.workflow_state == "REFINING": self.confirm_boundaries()

    def _drawing_click(self, x, y):
        if self.read_only or self.workflow_state != "DRAWING": return
        point = PlanPoint(x, y)
        if self._drawing_vertices and len(self._drawing_vertices) >= 3:
            first = self._drawing_vertices[0]
            if ((point.x-first.x) ** 2 + (point.y-first.y) ** 2) ** .5 <= 8 / max(self.plan_view.transform().m11(), 1e-9):
                self.finish_polygon(); return
        self._drawing_vertices.append(point); self.draw_geometry()

    def _drawing_move(self, x, y):
        if self.workflow_state == "DRAWING" and self._drawing_vertices:
            self._drawing_cursor = PlanPoint(x, y); self.draw_geometry()

    def _current_draft_polygon(self):
        return PlanPolygon(tuple(self._drawing_vertices + [self._drawing_vertices[0]]))

    def _refresh_refinement_candidates(self):
        try:
            polygon = self._current_draft_polygon(); validate_simple_polygon(polygon)
            self._candidate_preview = self.area_service.generate_candidates(polygon)
        except (ValueError, IndexError):
            self._candidate_preview = []

    def _handle_moved(self, index, x, y):
        if self.workflow_state != "REFINING" or index >= len(self._drawing_vertices): return
        self._drawing_vertices[index] = PlanPoint(x, y)
        try: validate_simple_polygon(self._current_draft_polygon()); valid = True
        except ValueError: valid = False
        self._update_refinement_path(valid)

    def _handle_released(self, _index):
        self._refresh_refinement_candidates(); self.draw_geometry()

    def draw_geometry(self):
        self._vertex_handles = []; self._refinement_path_item = None; self.scene.clear()
        self._draw_project_lines()
        if self.selected_area:
            self._path_item(self.selected_area.final_geometry_frozen, QPen(QColor(20, 120, 200), 3),
                            QBrush(QColor(30, 140, 220, 55)), 22)
        self._draw_polygon_preview()
        for candidate in self._candidate_preview:
            self._path_item(candidate.geometry, QPen(QColor(255, 120, 0), 4), z=75)
        if self._show_grid: self._add_grid()

    def _draw_project_lines(self):
        dataset = self.state.active_dataset()
        if not dataset or not self._show_project_lines: return
        pen = QPen(self.palette().color(self.palette().ColorRole.Mid), 0.8)
        for line in dataset.lines:
            if len(line.points) < 2: continue
            path = QPainterPath(); path.moveTo(line.points[0].x, -line.points[0].y)
            for point in line.points[1:]: path.lineTo(point.x, -point.y)
            item = QGraphicsPathItem(path); item.setPen(pen); item.setOpacity(.55); item.setZValue(10)
            item.setData(PROJECT_LINE_ROLE, True); item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(item)

    def _path_item(self, geometry, pen, brush=None, z=20):
        points = geometry.ring if isinstance(geometry, PlanPolygon) else geometry.points
        path = QPainterPath(QPointF(points[0].x, -points[0].y))
        for point in points[1:]: path.lineTo(point.x, -point.y)
        item = QGraphicsPathItem(path); item.setPen(pen)
        if brush is not None: item.setBrush(brush)
        item.setZValue(z); self.scene.addItem(item); return item

    def _draw_polygon_preview(self):
        if not self._drawing_vertices: return
        points = self._drawing_vertices + ([self._drawing_cursor] if self._drawing_cursor else [])
        path = QPainterPath(QPointF(points[0].x, -points[0].y))
        for point in points[1:]: path.lineTo(point.x, -point.y)
        if len(self._drawing_vertices) >= 3: path.lineTo(points[0].x, -points[0].y)
        item = QGraphicsPathItem(path); item.setPen(QPen(QColor(0, 130, 230), 2, Qt.PenStyle.DashLine))
        item.setBrush(QColor(0, 130, 230, 35)); item.setZValue(80)
        item.setData(ASSESSMENT_SELECTION_ROLE, True); self.scene.addItem(item); self._refinement_path_item = item
        if self.workflow_state == "REFINING":
            for index, point in enumerate(self._drawing_vertices):
                handle = PolygonVertexHandle(index, point, self._handle_moved, self._handle_released)
                self.scene.addItem(handle); self._vertex_handles.append(handle)

    def _update_refinement_path(self, valid=True):
        if self._refinement_path_item is None or not self._drawing_vertices: return
        path = QPainterPath(QPointF(self._drawing_vertices[0].x, -self._drawing_vertices[0].y))
        for point in self._drawing_vertices[1:]: path.lineTo(point.x, -point.y)
        path.closeSubpath(); self._refinement_path_item.setPath(path)
        self._refinement_path_item.setPen(QPen(QColor(0, 130, 230) if valid else QColor(210, 40, 40), 2, Qt.PenStyle.DashLine))

    def _add_grid(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isNull(): return
        step = max(max(rect.width(), rect.height()) / 10, 1)
        pen = QPen(self.palette().color(self.palette().ColorRole.Midlight), 0)
        x = rect.left()
        while x <= rect.right(): self.scene.addLine(x, rect.top(), x, rect.bottom(), pen).setZValue(0); x += step
        y = rect.top()
        while y <= rect.bottom(): self.scene.addLine(rect.left(), y, rect.right(), y, pen).setZValue(0); y += step
