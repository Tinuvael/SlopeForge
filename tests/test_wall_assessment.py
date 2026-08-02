from copy import deepcopy
from datetime import date, datetime, timezone
import json
import pytest
from prototype_2d.domain import (AssessmentArea,AssessmentAreaGeometryRevision,AssessmentDomainState,AssessmentEventLink,BlastEvent,PlanPoint,PlanPolygon)
from prototype_2d.wall_assessment import *

@pytest.fixture
def area():
    p=PlanPolygon((PlanPoint(0,0),PlanPoint(1,0),PlanPoint(1,1),PlanPoint(0,0)))
    r=AssessmentAreaGeometryRevision("AA-1-R001","AA-1",1,datetime.now(timezone.utc),"D",p,p,100,110,())
    return AssessmentArea("AA-1","A",date.today(),[r],r.id)

def test_template_maxima_and_threshold_ownership():
    for tid in BUILTIN_TEMPLATES:
        t=get_template(tid)
        assert t.section(DESIGN).maximum_points==t.section(CONDITION).maximum_points==100
        assert sum(c.maximum_score for c in t.section(DESIGN).criteria)==100
        assert sum(c.maximum_score for c in t.section(CONDITION).criteria)==100
        assert (t.face_condition_threshold,t.design_achievement_threshold)==(.60,.65)

@pytest.mark.parametrize("value,score",[(0,50),(.1,25),(3,25),(3.1,10),(5,10),(5.1,0)])
def test_controlled_angle(value,score): assert score_numeric("bench_angle",value,"controlled_blasting_v1")==score
@pytest.mark.parametrize("value,score",[(0,40),(.1,36),(1,36),(2.4,28),(9,4),(9.1,0),(10,0)])
def test_plain_angle_next_worse(value,score): assert score_numeric("bench_angle",value,"no_controlled_blasting_v1")==score
@pytest.mark.parametrize("criterion,value,template,score",[("berm_width",0,"controlled_blasting_v1",40),("berm_width",1,"controlled_blasting_v1",25),("berm_width",3,"controlled_blasting_v1",0),("toe_position",.5,"controlled_blasting_v1",8),("toe_position",1,"no_controlled_blasting_v1",5),("visible_drillhole_traces",75,"controlled_blasting_v1",15),("crest_loss",2.5,"controlled_blasting_v1",5)])
def test_numeric_matrices(criterion,value,template,score): assert score_numeric(criterion,value,template)==score

def test_detection_confirmed_only_and_manual_reason(area):
    contour=BlastEvent("BE","Contour","contour",None,105)
    area.event_links=[AssessmentEventLink("BE","G","suggested","automatic",assessment_area_geometry_revision_id=area.active_geometry_revision_id)]
    state=AssessmentDomainState(blast_events=[contour],assessment_areas=[area]); svc=AssessmentAreaEvaluationService(state)
    assert svc.detect_template(area)[0]=="no_controlled_blasting_v1"
    area.event_links[0].status="confirmed"; assert svc.detect_template(area)[0]=="controlled_blasting_v1"
    with pytest.raises(ValueError): svc.new_evaluation(area,"no_controlled_blasting_v1")

def test_categories_damage_and_manual_rules():
    t=get_template("controlled_blasting_v1")
    r=AssessmentCriterionResult("loose_blocks","x",CONDITION,selected_option_id="none"); assert score_result(r,t)==20
    r=AssessmentCriterionResult("damage","x",CONDITION,raw_numeric_value=3)
    assert score_result(r,t) is None
    r.selected_option_id="low"
    with pytest.raises(ValueError): score_result(r,t)
    r.override_reason="осмотр"; assert score_result(r,t)==15
    r=AssessmentCriterionResult("open_cracks","x",CONDITION,selected_option_id="many_open",manual_score=11,override_reason="x")
    with pytest.raises(ValueError): score_result(r,t)
    r.manual_score=5; r.override_reason=""
    with pytest.raises(ValueError): score_result(r,t)

def complete_revision(template_id="controlled_blasting_v1"):
    t=get_template(template_id); results=[]
    for s in t.sections:
        for c in s.criteria:
            r=AssessmentCriterionResult(c.id,c.name,s.id,maximum_score=c.maximum_score,manual_score=c.maximum_score,override_reason="контроль")
            results.append(r)
    return AssessmentAreaEvaluationRevision("","E",0,datetime.now(timezone.utc),date.today(),"Иванов","draft","AA-1-R001",t.id,t.version,t.to_dict(),template_id.startswith("controlled"),"manual",criterion_results=results)

def test_indices_quadrants_draft_and_completion():
    r=complete_revision(); calculate_revision(r,True); assert r.design_achievement_index==r.face_condition_index==1 and r.result_quadrant=="good_results"
    t=get_template("controlled_blasting_v1")
    assert classify(.7,.5,t)[0]=="geometry_achieved_condition_insufficient"
    assert classify(.5,.7,t)[0]=="condition_good_geometry_unacceptable"
    assert classify(.5,.5,t)[0]=="unacceptable"
    draft=deepcopy(r); draft.criterion_results=[]; calculate_revision(draft); assert draft.result_quadrant is None
    with pytest.raises(ValueError): calculate_revision(draft,True)

def test_versioning_roundtrip_old_json_archive_and_geometry_history(area):
    state=AssessmentDomainState(assessment_areas=[area]); svc=AssessmentAreaEvaluationService(state); evaluation,draft=svc.new_evaluation(area)
    draft=complete_revision("no_controlled_blasting_v1"); draft.evaluation_id=evaluation.id
    first=evaluation.save_revision(draft,"completed"); edit=deepcopy(first); edit.comments="changed"; second=evaluation.save_revision(edit,"completed")
    assert second.revision_number==2 and first.comments=="" and first.assessment_area_geometry_revision_id=="AA-1-R001"
    restored=AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.evaluations[0].revisions[0].result_quadrant=="good_results"
    old=state.to_dict(); old.pop("evaluations"); assert AssessmentDomainState.from_dict(old).evaluations==[]
    area.archive()
    with pytest.raises(ValueError): svc.new_evaluation(area)
