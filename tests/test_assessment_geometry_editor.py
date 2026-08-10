from datetime import date

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication, QDialog

from prototype_2d.assessment_area_service import AssessmentAreaService
from domain.geometry.types import PlanPoint, PlanPolygon
from prototype_2d.domain import AssessmentDomainState
from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
from ui.editors.assessment_geometry_editor import (
    ASSESSMENT_HANDLE_ROLE, PROJECT_LINE_ROLE, AssessmentGeometryEditorWidget,
)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def state(tmp_path):
    source = tmp_path / "project.csv"
    source.write_text(
        "XP,YP,ZP,SID,PTN\n0,2,600,lo,1\n10,2,600,lo,2\n"
        "0,8,620,hi,1\n10,8,620,hi,2\n", encoding="utf-8")
    result = AssessmentDomainState()
    ProjectLinesDatasetService(result).import_dataset(source)
    return result


def polygon():
    return PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10),
                        PlanPoint(0, 10), PlanPoint(0, 0)))


class AcceptedCandidateDialog:
    def __init__(self, candidates, parent=None):
        self.candidates = candidates
        self.area_name = QtWidgets.QLineEdit("Area")
        self.area_date = QtWidgets.QDateEdit()

    def exec(self):
        return QDialog.DialogCode.Accepted

    def selected_candidates(self):
        return self.candidates


def prepare(editor):
    editor.start_new_area()
    for point in polygon().ring[:-1]:
        editor._drawing_click(point.x, point.y)
    editor.finish_polygon()


def test_drawing_undo_refinement_cancel_and_project_lines(state, app):
    editor = AssessmentGeometryEditorWidget(state, lambda: None)
    assert [item for item in editor.scene.items() if item.data(PROJECT_LINE_ROLE)]
    editor.set_project_lines_visible(False)
    assert not [item for item in editor.scene.items() if item.data(PROJECT_LINE_ROLE)]
    editor.start_new_area(); editor._drawing_click(0, 0); editor._drawing_click(10, 0)
    editor.undo_vertex(); assert editor._drawing_vertices == [PlanPoint(0, 0)]
    editor.cancel_workflow()
    assert not editor.has_active_workflow() and state.assessment_areas == []
    editor.deleteLater(); assert app


def test_create_emits_id_saves_and_preserves_selected_fragments(monkeypatch, state, app):
    import ui.editors.assessment_geometry_editor as module
    monkeypatch.setattr(module, "AssessmentCandidateDialog", AcceptedCandidateDialog)
    saves = []; created = []
    editor = AssessmentGeometryEditorWidget(state, lambda: saves.append(True))
    editor.area_created.connect(created.append)
    prepare(editor)
    assert len([item for item in editor.scene.items() if item.data(ASSESSMENT_HANDLE_ROLE)]) == 4
    editor.confirm_boundaries()
    assert saves == [True] and created == [state.assessment_areas[0].id]
    assert len(state.assessment_areas[0].horizon_slices) == 2
    assert not editor.has_active_workflow()
    editor.deleteLater(); assert app


def test_candidate_cancellation_keeps_refinement_without_persisting(monkeypatch, state, app):
    import ui.editors.assessment_geometry_editor as module
    class Cancelled(AcceptedCandidateDialog):
        def exec(self): return QDialog.DialogCode.Rejected
    monkeypatch.setattr(module, "AssessmentCandidateDialog", Cancelled)
    saves = []; editor = AssessmentGeometryEditorWidget(state, lambda: saves.append(True))
    prepare(editor); editor.confirm_boundaries()
    assert editor.workflow_state == "REFINING" and saves == [] and state.assessment_areas == []
    editor.deleteLater(); assert app


def test_edit_creates_revision_and_emits_existing_id(monkeypatch, state, app):
    import ui.editors.assessment_geometry_editor as module
    monkeypatch.setattr(module, "AssessmentCandidateDialog", AcceptedCandidateDialog)
    service = AssessmentAreaService(state)
    area = service.create_area(name="Original", assessment_date=date.today(), selection_polygon=polygon(),
                               selected_fragments=service.generate_candidates(polygon()))
    first_revision = area.active_geometry_revision_id; revised = []
    editor = AssessmentGeometryEditorWidget(state, lambda: None)
    editor.area_revised.connect(revised.append); editor.start_edit(area.id)
    editor._handle_moved(1, 9, 0); editor._handle_released(1); editor.confirm_boundaries()
    assert revised == [area.id] and len(area.geometry_revisions) == 2
    assert area.geometry_revisions[0].id == first_revision and area.active_geometry_revision_id != first_revision
    editor.deleteLater(); assert app


def test_persistence_failure_rolls_back_and_reports_no_completion(monkeypatch, state, app):
    import ui.editors.assessment_geometry_editor as module
    monkeypatch.setattr(module, "AssessmentCandidateDialog", AcceptedCandidateDialog)
    def fail(): raise RuntimeError("database unavailable")
    editor = AssessmentGeometryEditorWidget(state, fail); emitted = []
    editor.area_created.connect(emitted.append); prepare(editor)
    with pytest.raises(RuntimeError, match="database unavailable"):
        editor.confirm_boundaries()
    assert state.assessment_areas == [] and emitted == [] and editor.workflow_state == "REFINING"
    editor.deleteLater(); assert app
