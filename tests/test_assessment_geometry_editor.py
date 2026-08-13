from datetime import date
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication

from application.services.assessment_areas import AssessmentAreaService
from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.geometry import ProjectLineSpan, StraightConnector, extract_project_line_span
from ui.editors.assessment_geometry_editor import (PROJECT_LINE_ROLE, SNAP_MARKER_ROLE,
                                                    AssessmentGeometryEditorWidget)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def state(tmp_path):
    source = tmp_path / "project.csv"
    source.write_text(
        "XP,YP,ZP,SID,PTN\n0,10,110,A,1\n5,12,115,A,2\n10,10,120,A,3\n"
        "0,0,90,B,1\n5,-2,95,B,2\n10,0,100,B,3\n", encoding="utf-8")
    result = AssessmentDomainState()
    ProjectLinesDatasetService(result).import_dataset(source)
    return result


def committer(state):
    def commit(**values):
        service = AssessmentAreaService(state)
        area_id = values.pop("assessment_area_id")
        if area_id:
            area = next(item for item in state.assessment_areas if item.id == area_id)
            service.revise_area(area, boundary=values["boundary"])
        else:
            area = service.create_area(name=values["name"], assessment_date=values["assessment_date"],
                                       boundary=values["boundary"])
        return SimpleNamespace(area_id=area.id)
    return commit


def test_editor_starts_idle_and_navigation_does_not_commit(state, app):
    editor = AssessmentGeometryEditorWidget(state, committer(state))
    assert editor.workflow_state == "IDLE"
    assert editor._segments == [] and editor._first_point is None
    assert editor.plan_view.dragMode() == editor.plan_view.DragMode.ScrollHandDrag


def test_creation_page_does_not_auto_start_drawing():
    from pathlib import Path
    source = Path("ui/pages/assessment_area_creation_page.py").read_text(encoding="utf-8")
    constructor = source[source.index("    def __init__"):source.index("    def _start_drawing")]
    assert "self._start_drawing()" not in constructor
    assert '"Wheel: zoom · Middle drag: pan' in source


def test_trace_preview_commit_jump_and_new_active_source(state, app):
    editor = AssessmentGeometryEditorWidget(state, committer(state)); editor.start_new_area()
    editor._drawing_click(1, 10.4)  # snaps to curved A
    editor._drawing_move(9, 10.4)
    candidate = editor._candidate.anchor
    line_a = state.active_dataset().lines[0]
    preview = editor._segment_points(extract_project_line_span(line_a, editor._last_anchor, candidate))
    assert len(preview) == 3 and preview[1].y == 12  # no endpoint chord
    assert [item for item in editor.scene.items() if item.data(SNAP_MARKER_ROLE)]
    assert len([item for item in editor.scene.items() if item.data(PROJECT_LINE_ROLE)]) == 2
    editor._drawing_click(9, 10.4)
    assert isinstance(editor._segments[-1], ProjectLineSpan)
    assert editor._segments[-1].frozen_trace_xyz[1].y == 12

    editor._drawing_move(9, .4)  # hover B: active source remains A
    assert editor._last_anchor.source_line_id == "A"
    editor._drawing_click(9, .4)
    assert isinstance(editor._segments[-1], StraightConnector)
    assert editor._last_anchor.source_line_id == "B"
    editor._drawing_click(1, .4)
    assert isinstance(editor._segments[-1], ProjectLineSpan)
    assert editor._segments[-1].frozen_trace_xyz[1].y == -2


def test_draw_close_save_emits_and_does_not_restart(state, app):
    editor = AssessmentGeometryEditorWidget(state, committer(state)); emitted=[]
    editor.area_created.connect(emitted.append); editor.start_new_area()
    editor._drawing_click(0,10); editor._drawing_click(10,10)
    editor._drawing_click(10,0); editor._drawing_click(0,0)
    editor.finish_polygon()
    assert editor.workflow_state == "CLOSED"
    saved_date=date(2026,8,13)
    editor.confirm_boundaries(name="West wall",assessment_date=saved_date)
    assert len(state.assessment_areas) == 1 and emitted == [state.assessment_areas[0].id]
    assert state.assessment_areas[0].name=="West wall" and state.assessment_areas[0].assessment_date==saved_date
    assert editor.workflow_state == "IDLE" and not editor.has_active_workflow()


def test_undo_closed_reopens_and_cancel_clears_draft(state, app):
    editor = AssessmentGeometryEditorWidget(state, committer(state)); editor.start_new_area()
    for point in ((0,10),(10,10),(10,0),(0,0)): editor._drawing_click(*point)
    editor.finish_polygon(); editor.undo_vertex()
    assert editor.workflow_state == "DRAWING"
    editor.cancel_workflow()
    assert editor.workflow_state == "IDLE" and editor._segments == []

def test_close_preserves_first_snapped_anchor(state, app):
    editor=AssessmentGeometryEditorWidget(state,committer(state)); editor.start_new_area()
    editor._drawing_click(0,10); first=editor._first_anchor
    editor._drawing_click(10,10); editor._drawing_click(10,0); editor._drawing_click(0,0)
    editor.finish_polygon()
    assert editor._segments[-1].end_anchor==first


def test_page_owns_name_and_date_fields_and_grid_is_not_exposed():
    from pathlib import Path
    source=Path("ui/pages/assessment_area_creation_page.py").read_text(encoding="utf-8")
    assert "self.area_name" in source and "self.assessment_date" in source
    assert "name=self.area_name.text()" in source
    assert "Grid" not in source
