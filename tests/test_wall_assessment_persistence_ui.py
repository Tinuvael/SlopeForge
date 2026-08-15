from copy import deepcopy
from datetime import date, datetime, timezone
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="Qt unavailable", exc_type=ImportError)
from PySide6.QtWidgets import QApplication
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.blasting.entities import BlastEvent
from domain.assessment.entities import AssessmentArea, AssessmentEventLink
from tests.assessment_boundary_fixtures import geometry_revision
from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.evaluation import (AssessmentAreaEvaluationService, AssessmentCriterionResult,
 CONDITION, DESIGN, calculate_revision)
from ui.editors.assessment_evaluation_editor import AssessmentAreaEvaluationDialog, DAMAGE_WARNING, NullableDoubleSpinBox


def app(): return QApplication.instance() or QApplication([])

def make_state():
    polygon=PlanPolygon((PlanPoint(0,0),PlanPoint(2,0),PlanPoint(2,2),PlanPoint(0,0)))
    geometry=geometry_revision("AA-1-R001","AA-1",1,datetime.now(timezone.utc),polygon,dataset_id="D",minimum=100,maximum=110)
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
    from domain.assessment.evaluation import get_template
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
    saved=evaluation.save_revision(draft,"completed")
    restored=AssessmentDomainState.from_dict(state.to_dict()); revision=restored.evaluations[0].active_revision()
    assert revision.status=="completed" and revision.design_inputs==saved.design_inputs
    assert revision.face_condition_inputs==saved.face_condition_inputs
    assert [(r.criterion_id,r.raw_numeric_value,r.selected_option_id,r.manual_score,r.override_reason,r.accepted_score) for r in revision.criterion_results]==[(r.criterion_id,r.raw_numeric_value,r.selected_option_id,r.manual_score,r.override_reason,r.accepted_score) for r in saved.criterion_results]
    assert (revision.design_achievement_index,revision.face_condition_index,revision.result_quadrant)==(1.0,saved.face_condition_index,saved.result_quadrant)

def test_dialog_restores_without_mutating_source_and_nullable_zero():
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); source=deepcopy(draft); dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    assert dialog.shortfall.nullable_value()==0 and dialog.deficit.nullable_value()==0 and dialog.toe.nullable_value()==0
    assert dialog.editors["visible_drillhole_traces"].input.nullable_value()==90
    assert dialog.editors["loose_blocks"].input.currentData()=="several_small"
    assert dialog.editors["damage"].manual_score.nullable_value()==8 and dialog.editors["damage"].override_reason=="Экспертная оценка"
    assert draft.to_dict()==source.to_dict() and not dialog._dirty
    blank=NullableDoubleSpinBox(); assert blank.nullable_value() is None; blank.set_nullable_value(0); assert blank.nullable_value()==0
    dialog._allow_close=True; dialog.close()

def test_damage_intermediate_manual_workflow_and_russian_table(monkeypatch):
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    editor=dialog.editors["damage"]; editor.input.set_nullable_value(1); editor.manual_score.clear_value(); dialog.refresh(False)
    assert DAMAGE_WARNING in editor.validation.text() and dialog._preview.face_condition_index is None
    monkeypatch.setattr(QtWidgets.QInputDialog,"getText",lambda *_args,**_kwargs:("Экспертный осмотр",True)); editor.manual_score.set_nullable_value(8); dialog.refresh(False)
    assert dialog._preview.design_achievement_index==1 and dialog._preview.face_condition_index is not None and dialog.plot.design==1
    assert "Несколько небольших блоков" in dialog.editors["loose_blocks"].input.currentText()
    assert "Твёрдая подошва" in dialog.editors["face_profile"].input.currentText()
    dialog._allow_close=True; dialog.close()

def test_dialog_initialization_does_not_collect_before_restore(monkeypatch):
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); calls=[]
    original=AssessmentAreaEvaluationDialog.collect
    def checked(self):
        calls.append(self.shortfall.nullable_value()); return original(self)
    monkeypatch.setattr(AssessmentAreaEvaluationDialog,"collect",checked)
    dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    assert calls and calls[0]==0
    dialog._allow_close=True; dialog.close()

def test_direct_geometry_inputs_are_canonical_and_live_preview_does_not_save():
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); calls=[]
    dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:calls.append(True))
    dialog.shortfall.set_nullable_value(3); dialog.deficit.set_nullable_value(1.5); dialog.toe.set_nullable_value(.8)
    collected=dialog.collect()
    assert collected.design_inputs=={
        "bench_angle_shortfall_deg":3.0,"berm_width_deficit_m":1.5,
        "toe_offset_from_design_m":.8,
    }
    assert not ({"design_bench_face_angle_deg","actual_bench_face_angle_deg","design_berm_width_m","actual_berm_width_m"}&collected.design_inputs.keys())
    assert calls==[] and dialog.angle_score.text()!="Required"
    assert not hasattr(dialog,"design_table") and not hasattr(dialog,"condition_table")
    assert not hasattr(dialog,"scoring_details")
    dialog._allow_close=True; dialog.close()

def test_legacy_geometry_payload_is_presented_without_mutating_history():
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area)
    draft.design_inputs={"design_bench_face_angle_deg":60,"actual_bench_face_angle_deg":57,
                         "design_berm_width_m":8,"actual_berm_width_m":6.5,
                         "toe_offset_from_design_m":.4,"measurement_method":"survey","measurement_notes":"legacy"}
    original=deepcopy(draft)
    dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    assert dialog.shortfall.nullable_value()==3 and dialog.deficit.nullable_value()==1.5
    assert draft.to_dict()==original.to_dict()
    assert set(dialog.collect().design_inputs)=={"bench_angle_shortfall_deg","berm_width_deficit_m","toe_offset_from_design_m"}
    dialog._allow_close=True; dialog.close()

def test_manual_matrix_reason_is_only_available_for_manual_selection():
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area)
    automatic=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    assert automatic.override_reason.isHidden()
    automatic._allow_close=True; automatic.close()
    draft.controlled_blasting_detection_source="manual_override"; draft.change_reason="Engineering review"
    manual=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    assert not manual.override_reason.isHidden() and manual.override_reason.text()=="Engineering review"
    manual._allow_close=True; manual.close()

def test_compact_manual_score_prompt_cancel_clear_and_geometry_control(monkeypatch):
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area); dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,lambda *_:None)
    editor=dialog.geometry_editors["bench_angle"]
    assert not hasattr(editor,"override_panel") and not hasattr(editor,"override_toggle")
    assert editor.manual_score.maximum()==editor.criterion.maximum_score
    assert editor.manual_score.parentWidget() is editor and editor.help_button.toolTip()
    monkeypatch.setattr(QtWidgets.QInputDialog,"getText",lambda *_args,**_kwargs:("Survey review",True))
    editor.manual_score.set_nullable_value(12)
    assert editor.override_reason=="Survey review" and not dialog.shortfall.isEnabled()
    assert dialog._preview.criterion_results[0].accepted_score==12
    editor.manual_score.clear_value()
    assert editor.override_reason is None and dialog.shortfall.isEnabled()
    monkeypatch.setattr(QtWidgets.QInputDialog,"getText",lambda *_args,**_kwargs:("",False))
    editor.manual_score.set_nullable_value(10)
    assert editor.manual_score.nullable_value() is None and dialog.shortfall.isEnabled()
    dialog._allow_close=True; dialog.close()

def test_storage_failure_does_not_report_success_or_create_revision(monkeypatch):
    app(); state,area=make_state(); evaluation,draft=filled_draft(state,area)
    def failure(*_args): raise OSError("disk full")
    dialog=AssessmentAreaEvaluationDialog(area,evaluation,draft,failure)
    monkeypatch.setattr(QtWidgets.QMessageBox,"critical",lambda *_args,**_kwargs: QtWidgets.QMessageBox.StandardButton.Ok)
    assert dialog.save("completed") is False and evaluation.revisions==[] and state.evaluations==[]
    dialog._allow_close=True; dialog.close()
