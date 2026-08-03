from copy import deepcopy
from datetime import date, datetime, timezone
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="Qt unavailable", exc_type=ImportError)
from PySide6.QtWidgets import QApplication
from prototype_2d.blast_event_storage import load_blast_event_state, save_blast_event_state
from prototype_2d.domain import (AssessmentArea, AssessmentAreaGeometryRevision, AssessmentDomainState,
 AssessmentEventLink, BlastEvent, PlanPoint, PlanPolygon)
from prototype_2d.wall_assessment import (AssessmentAreaEvaluationService, AssessmentCriterionResult,
 CONDITION, DESIGN, calculate_revision)
from ui.prototype_2d.wall_assessment_dialog import AssessmentAreaEvaluationDialog, DAMAGE_WARNING, NullableDoubleSpinBox


def app(): return QApplication.instance() or QApplication([])

def make_state():
    polygon=PlanPolygon((PlanPoint(0,0),PlanPoint(2,0),PlanPoint(2,2),PlanPoint(0,0)))
    geometry=AssessmentAreaGeometryRevision("AA-1-R001","AA-1",1,datetime.now(timezone.utc),"D",polygon,polygon,100,110,())
    link=AssessmentEventLink("BE-1","BE-1-R001","confirmed","manual",id="L-1",assessment_area_geometry_revision_id=geometry.id)
    area=AssessmentArea("AA-1","Wall",date.today(),[geometry],geometry.id,[link])
    return AssessmentDomainState(blast_events=[BlastEvent("BE-1","Контур","contour",date.today(),105)],assessment_areas=[area]),area

def filled_draft(state,area):
    evaluation,draft=AssessmentAreaEvaluationService(state).new_evaluation(area)
    draft.inspector="Иванов"
    draft.design_inputs={"design_bench_face_angle_deg":65.0,"actual_bench_face_angle_deg":66.0,"bench_angle_shortfall_deg":0.0,"design_berm_width_m":10.0,"actual_berm_width_m":10.0,"berm_width_deficit_m":0.0,"toe_offset_from_design_m":0.0,"measurement_method":"рулетка","measurement_notes":"контроль"}
    values={"bench_angle":0,"berm_width":0,"toe_position":0,"visible_drillhole_traces":90,"crest_loss":1,"damage":1}
    options={"loose_blocks":"several_small","face_profile":"hard_toe","open_cracks":"closed"}
    results=[]
    template=AssessmentAreaEvaluationService(state).detect_template(area)[0]
    from prototype_2d.wall_assessment import get_template
    for section in get_template(template).sections:
        for criterion in section.criteria:
            results.append(AssessmentCriterionResult(criterion.id,criterion.name,section.id,
                raw_numeric_value=values.get(criterion.id),selected_option_id=options.get(criterion.id),
                manual_score=8 if criterion.id=="damage" else None,override_reason="Экспертная оценка" if criterion.id=="damage" else None,
                notes="осмотр" if criterion.id=="damage" else "",maximum_score=criterion.maximum_score))
    draft.criterion_results=results
    draft.face_condition_inputs={k:v for k,v in values.items() if k not in {"bench_angle","berm_width","toe_position"}}|options
    calculate_revision(draft,True)
    return evaluation,draft

def test_new_evaluation_is_transient_and_empty_legacy_is_safe():
    state,area=make_state(); evaluation,draft=AssessmentAreaEvaluationService(state).new_evaluation(area)
    assert state.evaluations==[] and evaluation.active_revision() is None
    state.evaluations.append(evaluation)
    # The window workflow can reuse this object; the domain method is safe.
    assert evaluation.active_revision() is None and draft.evaluation_id==evaluation.id

def test_draft_revision_stores_all_inputs_and_is_independent():
    state,area=make_state(); evaluation,draft=filled_draft(state,area); state.evaluations.append(evaluation)
    first=evaluation.save_revision(draft,"draft")
    assert first.design_inputs["design_bench_face_angle_deg"]==65
    assert first.face_condition_inputs["visible_drillhole_traces"]==90
    assert next(r for r in first.criterion_results if r.criterion_id=="loose_blocks").selected_option_id=="several_small"
    damage=next(r for r in first.criterion_results if r.criterion_id=="damage")
    assert (damage.manual_score,damage.override_reason)==(8,"Экспертная оценка")
    edit=deepcopy(first); edit.design_inputs["actual_bench_face_angle_deg"]=60; evaluation.save_revision(edit,"draft")
    assert first.design_inputs["actual_bench_face_angle_deg"]==66

def test_completed_end_to_end_save_load_restores_everything(tmp_path):
    state,area=make_state(); evaluation,draft=filled_draft(state,area); state.evaluations.append(evaluation)
    saved=evaluation.save_revision(draft,"completed"); path=tmp_path/"assessment.json"; save_blast_event_state(state,path)
    restored=load_blast_event_state(path); revision=restored.evaluations[0].active_revision()
    assert revision.status=="completed" and revision.design_inputs==saved.design_inputs
    assert revision.face_condition_inputs==saved.face_condition_inputs
    assert [(r.criterion_id,r.raw_numeric_value,r.selected_option_id,r.manual_score,r.override_reason,r.accepted_score) for r in revision.criterion_results]==[(r.criterion_id,r.raw_numeric_value,r.selected_option_id,r.manual_score,r.override_reason,r.accepted_score) for r in saved.criterion_results]
    assert (revision.design_achievement_index,revision.face_condition_index,revision.result_quadrant)==(1.0,saved.face_condition_index,saved.result_quadrant)

def test_dialog_restores_without_mutating_source_and_nullable_zero():
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); source=deepcopy(draft); dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    assert dialog.da.nullable_value()==65 and dialog.aa.nullable_value()==66 and dialog.toe.nullable_value()==0
    assert dialog.editors["visible_drillhole_traces"].input.nullable_value()==90
    assert dialog.editors["loose_blocks"].input.currentData()=="several_small"
    assert dialog.editors["damage"].manual_score.nullable_value()==8 and dialog.editors["damage"].reason.text()=="Экспертная оценка"
    assert draft.to_dict()==source.to_dict() and not dialog._dirty
    blank=NullableDoubleSpinBox(); assert blank.nullable_value() is None; blank.set_nullable_value(0); assert blank.nullable_value()==0
    dialog._allow_close=True; dialog.close()

def test_damage_intermediate_manual_workflow_and_russian_table():
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    editor=dialog.editors["damage"]; editor.input.set_nullable_value(1); editor.manual_score.clear_value(); editor.reason.clear(); dialog.refresh(False)
    assert DAMAGE_WARNING in editor.validation.text() and dialog._preview.face_condition_index is None
    editor.manual_score.set_nullable_value(8); editor.reason.setText("Экспертный осмотр"); dialog.refresh(False)
    assert dialog._preview.design_achievement_index==1 and dialog._preview.face_condition_index is not None and dialog.plot.design==1
    texts=[dialog.condition_table.item(row,col).text() for row in range(dialog.condition_table.rowCount()) for col in range(dialog.condition_table.columnCount())]
    assert "Несколько небольших блоков" in texts and "several_small" not in texts and "Твёрдая подошва" in texts
    dialog._allow_close=True; dialog.close()

def test_dialog_initialization_does_not_collect_before_restore(monkeypatch):
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); calls=[]
    original=AssessmentAreaEvaluationDialog.collect
    def checked(self):
        calls.append(self.da.nullable_value()); return original(self)
    monkeypatch.setattr(AssessmentAreaEvaluationDialog,"collect",checked)
    dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    assert calls and calls[0]==65
    dialog._allow_close=True; dialog.close()

def test_storage_failure_does_not_report_success_or_create_revision(monkeypatch):
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area)
    def failure(*_args): raise OSError("disk full")
    dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,failure)
    monkeypatch.setattr(QtWidgets.QMessageBox,"critical",lambda *_args,**_kwargs: QtWidgets.QMessageBox.StandardButton.Ok)
    assert dialog.save("completed") is False and evaluation.revisions==[] and state.evaluations==[]
    dialog._allow_close=True; dialog.close()
