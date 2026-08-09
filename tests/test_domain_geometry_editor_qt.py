from types import SimpleNamespace
import pytest
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication,QDialog,QGraphicsView,QMessageBox
    from prototype_2d.domain import PlanPoint,PlanPolygon
    from ui.dialogs.domain_geometry_editor import DomainGeometryEditorDialog
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}",allow_module_level=True)

@pytest.fixture(scope="module")
def app(): return QApplication.instance() or QApplication([])

def polygon(x):
    points=(PlanPoint(x,0),PlanPoint(x+4,0),PlanPoint(x+4,4),PlanPoint(x,4)); return PlanPolygon(points+(points[0],))


def silence_warnings(monkeypatch):
    warnings=[]; monkeypatch.setattr(QMessageBox,"warning",lambda *args:warnings.append(args[-1])); return warnings


def test_dragged_vertex_survives_selection_and_project_lines_rerender(app):
    dialog=DomainGeometryEditorDialog((polygon(0),polygon(10)),(SimpleNamespace(points=((0,0),(20,20))),))
    dialog._select(0); dialog.handles[0].setPos(1,-2); dialog._select(1)
    assert dialog.polygons[0].ring[0]==PlanPoint(1,2)
    dialog.handles[0].setPos(11,-2); dialog.lines_toggle.setChecked(False)
    assert dialog.polygons[1].ring[0]==PlanPoint(11,2)


def test_manual_finish_rejects_invalid_and_accepts_valid(app,monkeypatch):
    warnings=silence_warnings(monkeypatch); dialog=DomainGeometryEditorDialog()
    dialog.vertices=[PlanPoint(0,0),PlanPoint(1,0),PlanPoint(2,0)]; dialog.drawing=True; dialog.finish_polygon()
    assert not dialog.polygons and warnings
    dialog.vertices=[PlanPoint(0,0),PlanPoint(4,4),PlanPoint(0,3),PlanPoint(3,0)]; dialog.finish_polygon()
    assert not dialog.polygons and len(warnings)==2
    dialog.vertices=[PlanPoint(0,0),PlanPoint(4,0),PlanPoint(4,4),PlanPoint(0,4)]; dialog.finish_polygon()
    assert len(dialog.polygons)==1


def test_polygon_made_invalid_by_handle_drag_cannot_save(app,monkeypatch):
    warnings=silence_warnings(monkeypatch); dialog=DomainGeometryEditorDialog((polygon(0),)); dialog._select(0)
    dialog.handles[1].setPos(4,-4); dialog.handles[2].setPos(0,-4); dialog.handles[3].setPos(4,0)
    dialog.save()
    assert dialog.result()==QDialog.DialogCode.Rejected and warnings


def test_cancel_keeps_caller_working_copy_unchanged(app):
    original=polygon(0); dialog=DomainGeometryEditorDialog((original,)); dialog._select(0); dialog.handles[0].setPos(2,-2); dialog.reject()
    assert original.ring[0]==PlanPoint(0,0) and dialog.result()==QDialog.DialogCode.Rejected


def test_adding_and_undoing_vertices_preserves_viewport(app):
    dialog=DomainGeometryEditorDialog((polygon(0),)); dialog.show(); app.processEvents()
    dialog.view.scale(1.7,1.7); dialog.view.centerOn(23,17)
    transform=dialog.view.transform(); center=dialog.view.mapToScene(dialog.view.viewport().rect().center())
    dialog.start_polygon(); dialog.add_vertex(1,1); dialog.add_vertex(2,1); dialog.undo_vertex()
    after_center=dialog.view.mapToScene(dialog.view.viewport().rect().center())
    assert dialog.view.transform()==transform
    assert abs(after_center.x()-center.x())<1 and abs(after_center.y()-center.y())<1


def test_add_polygon_uses_drawing_cursor_and_disables_hand_drag(app):
    dialog=DomainGeometryEditorDialog((polygon(0),))
    assert dialog.view.dragMode()==QGraphicsView.DragMode.ScrollHandDrag
    dialog.start_polygon()
    assert dialog.drawing
    assert dialog.view.dragMode()==QGraphicsView.DragMode.NoDrag
    assert dialog.view.viewport().cursor().shape()==Qt.CursorShape.CrossCursor


def test_finishing_or_cancelling_drawing_restores_navigation(app):
    dialog=DomainGeometryEditorDialog(); dialog.start_polygon()
    dialog.vertices=[PlanPoint(0,0),PlanPoint(4,0),PlanPoint(0,4)]; dialog.finish_polygon()
    assert not dialog.drawing
    assert dialog.view.dragMode()==QGraphicsView.DragMode.ScrollHandDrag
    assert dialog.view.viewport().cursor().shape()!=Qt.CursorShape.CrossCursor
    dialog.start_polygon(); dialog.reject()
    assert not dialog.drawing
    assert dialog.view.dragMode()==QGraphicsView.DragMode.ScrollHandDrag
    assert dialog.view.viewport().cursor().shape()!=Qt.CursorShape.CrossCursor


def test_project_lines_use_thin_cosmetic_unfilled_background_style(app):
    lines=(SimpleNamespace(points=((0,0),(20,20))),)
    dialog=DomainGeometryEditorDialog((polygon(0),),lines)
    assert len(dialog._line_items)==1
    item=dialog._line_items[0]
    assert item.pen().isCosmetic() and item.pen().widthF()==1
    assert item.opacity()<0.5 and item.brush().style()==Qt.BrushStyle.NoBrush
    dialog.render()
    assert len(dialog._line_items)==1
