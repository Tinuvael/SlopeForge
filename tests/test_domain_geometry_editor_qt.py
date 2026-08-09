from types import SimpleNamespace
import pytest
try:
    from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
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
