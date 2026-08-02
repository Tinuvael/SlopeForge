"""Versioned, serializable wall-performance assessment domain (no Qt dependencies)."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from math import ceil
from typing import Any
from uuid import uuid4

DESIGN = "design"
CONDITION = "face_condition"

@dataclass(frozen=True)
class AssessmentCriterionOption:
    id: str
    label: str
    score: float

@dataclass(frozen=True)
class AssessmentCriterionDefinition:
    id: str
    name: str
    section: str
    maximum_score: float
    kind: str
    options: tuple[AssessmentCriterionOption, ...] = ()
    thresholds: tuple[tuple[str, float], ...] = ()
    help_text: str = ""

@dataclass(frozen=True)
class AssessmentMatrixSection:
    id: str
    name: str
    criteria: tuple[AssessmentCriterionDefinition, ...]
    maximum_points: float = 100.0

@dataclass(frozen=True)
class AssessmentMatrixTemplate:
    id: str
    version: int
    name: str
    applicability: str
    sections: tuple[AssessmentMatrixSection, ...]
    face_condition_threshold: float = .60
    design_achievement_threshold: float = .65

    def criterion(self, criterion_id):
        return next((c for s in self.sections for c in s.criteria if c.id == criterion_id), None)
    def section(self, section_id): return next(s for s in self.sections if s.id == section_id)
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d):
        sections=[]
        for s in d["sections"]:
            criteria=[]
            for c in s["criteria"]:
                c=dict(c); c["options"]=tuple(AssessmentCriterionOption(**o) for o in c.get("options", [])); c["thresholds"]=tuple(tuple(x) for x in c.get("thresholds", []))
                criteria.append(AssessmentCriterionDefinition(**c))
            sections.append(AssessmentMatrixSection(s["id"],s["name"],tuple(criteria),s.get("maximum_points",100)))
        return cls(d["id"],d["version"],d["name"],d["applicability"],tuple(sections),d.get("face_condition_threshold",.6),d.get("design_achievement_threshold",.65))

def _opts(values): return tuple(AssessmentCriterionOption(*x) for x in values)
def _criterion(i,n,s,m,k="numeric",options=(),help_text=""): return AssessmentCriterionDefinition(i,n,s,m,k,_opts(options),(),help_text)
def _templates():
    common_design=lambda angle,toe: AssessmentMatrixSection(DESIGN,"Результаты проектирования",(
        _criterion("bench_angle","Угол откоса уступа",DESIGN,angle,help_text="Дефицит = max(проектный − фактический, 0)"),
        _criterion("berm_width","Ширина бермы",DESIGN,40),_criterion("toe_position","Положение подошвы",DESIGN,toe)))
    crest=_criterion("crest_loss","Состояние бровки",CONDITION,15)
    cracks=lambda: _criterion("open_cracks","Открытые трещины",CONDITION,10,"categorical",(("closed","Все трещины закрыты / отсутствуют",10),("many_open","Много открытых трещин",0)))
    damage=lambda m:_criterion("damage","Повреждение ранее ненарушенной породы",CONDITION,m,"damage",(("low","Менее 1 признака/м²",m),("extensive","Более 5 признаков/м²",0)),"При 1–5 признаках/м² требуется явное решение и причина")
    controlled=AssessmentMatrixTemplate("controlled_blasting_v1",1,"С контурным бурением","controlled",(
      common_design(50,10),AssessmentMatrixSection(CONDITION,"Показатели состояния борта",(
       _criterion("visible_drillhole_traces","Видимые следы контурных скважин",CONDITION,20),
       _criterion("loose_blocks","Свободные блоки",CONDITION,20,"categorical",(("none","Отсутствие валунов / свободных блоков",20),("several_small","Несколько небольших блоков",15),("large","Крупные блоки",10),("many","Много блоков",0))),
       _criterion("face_profile","Профиль борта",CONDITION,20,"categorical",(("straight","Прямой профиль",20),("hard_toe","Твёрдая подошва",10),("hanging_crest","Зависание породы на бровке",5),("irregular","Неровная поверхность борта",0))),crest,damage(15),cracks()))))
    plain=AssessmentMatrixTemplate("no_controlled_blasting_v1",1,"Без контурного бурения","not_controlled",(
      common_design(40,20),AssessmentMatrixSection(CONDITION,"Показатели состояния борта",(crest,
       _criterion("loose_blocks","Свободные блоки",CONDITION,25,"categorical",(("none","Отсутствуют",25),("several_small","Несколько небольших",15),("large","Крупные",10),("many","Много",0))),
       _criterion("face_profile","Профиль борта",CONDITION,30,"categorical",(("straight","Прямой профиль",30),("hard_toe","Твёрдая подошва",20),("hanging_face","Зависание на борту",15),("hanging_crest","Зависание на бровке",10),("irregular","Неровный борт",0))),damage(20),cracks()))))
    return {controlled.id:controlled,plain.id:plain}
BUILTIN_TEMPLATES=_templates()

def get_template(template_id): return BUILTIN_TEMPLATES[template_id]

@dataclass
class AssessmentCriterionResult:
    criterion_id: str
    criterion_name_snapshot: str
    section: str
    raw_numeric_value: float|None=None
    raw_text_value: str|None=None
    selected_option_id: str|None=None
    automatic_score: float|None=None
    manual_score: float|None=None
    accepted_score: float|None=None
    maximum_score: float=0
    is_manual_override: bool=False
    override_reason: str|None=None
    notes: str=""
    def validate(self):
        if self.manual_score is not None:
            if not 0 <= self.manual_score <= self.maximum_score: raise ValueError("Ручной балл вне допустимого диапазона")
            if not (self.override_reason or "").strip(): raise ValueError("Для ручного балла укажите причину")
        self.is_manual_override=self.manual_score is not None
        self.accepted_score=self.manual_score if self.manual_score is not None else self.automatic_score

@dataclass(frozen=True)
class LinkedEventSnapshot:
    assessment_event_link_id: str|None
    blast_event_id: str
    blast_event_name: str
    event_type: str
    linked_geometry_revision_id: str
    technical_card_revision_id: str|None
    event_elevation: float
    is_production: bool
    is_contour: bool

@dataclass
class AssessmentAreaEvaluationRevision:
    id: str; evaluation_id: str; revision_number: int; created_at: datetime
    assessment_date: date|None; inspector: str; status: str
    assessment_area_geometry_revision_id: str; matrix_template_id: str; matrix_template_version: int
    matrix_template_snapshot: dict[str,Any]; controlled_blasting_present: bool
    controlled_blasting_detection_source: str; design_inputs: dict[str,Any]=field(default_factory=dict)
    face_condition_inputs: dict[str,Any]=field(default_factory=dict); criterion_results: list[AssessmentCriterionResult]=field(default_factory=list)
    design_achievement_points: float|None=None; design_achievement_index: float|None=None
    face_condition_points: float|None=None; face_condition_index: float|None=None
    result_quadrant: str|None=None; result_label: str|None=None
    linked_event_snapshots: list[LinkedEventSnapshot]=field(default_factory=list); comments: str=""; recommendations: str=""; change_reason: str=""
    def to_dict(self):
        d=asdict(self); d["created_at"]=self.created_at.isoformat(); d["assessment_date"]=self.assessment_date.isoformat() if self.assessment_date else None; return d
    @classmethod
    def from_dict(cls,d):
        d=deepcopy(d); d["created_at"]=datetime.fromisoformat(d["created_at"]); d["assessment_date"]=date.fromisoformat(d["assessment_date"]) if d.get("assessment_date") else None
        d["criterion_results"]=[AssessmentCriterionResult(**x) for x in d.get("criterion_results",[])]; d["linked_event_snapshots"]=[LinkedEventSnapshot(**x) for x in d.get("linked_event_snapshots",[])]; return cls(**d)

@dataclass
class AssessmentAreaEvaluation:
    id: str; assessment_area_id: str; revisions: list[AssessmentAreaEvaluationRevision]=field(default_factory=list)
    active_revision_id: str|None=None; is_archived: bool=False; archived_at: datetime|None=None
    def active_revision(self): return next((r for r in self.revisions if r.id==self.active_revision_id),None)
    def save_revision(self,draft,status="draft"):
        saved=deepcopy(draft); saved.id=f"{self.id}-R{len(self.revisions)+1:03d}"; saved.evaluation_id=self.id; saved.revision_number=len(self.revisions)+1; saved.created_at=datetime.now(timezone.utc); saved.status=status
        calculate_revision(saved, require_complete=status=="completed")
        self.revisions.append(saved); self.active_revision_id=saved.id; return saved
    def to_dict(self): return {"id":self.id,"assessment_area_id":self.assessment_area_id,"revisions":[r.to_dict() for r in self.revisions],"active_revision_id":self.active_revision_id,"is_archived":self.is_archived,"archived_at":self.archived_at.isoformat() if self.archived_at else None}
    @classmethod
    def from_dict(cls,d): return cls(d["id"],d["assessment_area_id"],[AssessmentAreaEvaluationRevision.from_dict(x) for x in d.get("revisions",[])],d.get("active_revision_id"),d.get("is_archived",False),datetime.fromisoformat(d["archived_at"]) if d.get("archived_at") else None)

def score_numeric(criterion_id,value,template_id):
    v=float(value)
    if criterion_id=="bench_angle":
        if template_id=="controlled_blasting_v1": return 50 if v<=0 else 25 if v<=3 else 10 if v<=5 else 0
        return 40 if v<=0 else max(0,40-4*ceil(v)) # non-integers use next worse threshold
    if criterion_id=="berm_width": return 40 if v<=0 else 35 if v<1 else 25 if v<2 else 15 if v<3 else 0
    if criterion_id=="toe_position":
        maximum=10 if template_id=="controlled_blasting_v1" else 20
        return maximum if v<=0 else (8 if maximum==10 else 15) if v<1 else 5 if v<2 else 0
    if criterion_id=="visible_drillhole_traces": return 20 if v>=80 else 15 if v>=70 else 12 if v>=60 else 8 if v>=50 else 5 if v>=30 else 2 if v>=10 else 0
    if criterion_id=="crest_loss": return 15 if v<=0 else 12 if v<1 else 10 if v<2 else 5 if v<3 else 0
    raise ValueError("Неизвестный числовой критерий")

def score_result(result,template):
    c=template.criterion(result.criterion_id)
    result.maximum_score=c.maximum_score
    if c.kind=="categorical":
        option=next((o for o in c.options if o.id==result.selected_option_id),None); result.automatic_score=option.score if option else None
    elif c.kind=="damage":
        v=result.raw_numeric_value
        if v is not None and v<1: result.automatic_score=c.maximum_score
        elif v is not None and v>5: result.automatic_score=0
        elif result.selected_option_id:
            option=next((o for o in c.options if o.id==result.selected_option_id),None); result.automatic_score=option.score if option else None
            if v is not None and 1<=v<=5 and not (result.override_reason or "").strip(): raise ValueError("Для диапазона 1–5 укажите явное решение и причину")
        else: result.automatic_score=None
    else: result.automatic_score=score_numeric(c.id,result.raw_numeric_value,template.id) if result.raw_numeric_value is not None else None
    result.validate(); return result.accepted_score

QUADRANTS={"good_results":"Хорошие результаты","geometry_achieved_condition_insufficient":"Геометрическая форма достигнута, верхняя и нижняя бровки соответствуют","condition_good_geometry_unacceptable":"Хорошее состояние борта. Геометрическая форма неприемлема, верхняя и нижняя бровки не соответствуют","unacceptable":"Неприемлемые результаты"}
def classify(design,condition,template):
    key=("good_results" if condition>=template.face_condition_threshold and design>=template.design_achievement_threshold else "geometry_achieved_condition_insufficient" if design>=template.design_achievement_threshold else "condition_good_geometry_unacceptable" if condition>=template.face_condition_threshold else "unacceptable")
    return key,QUADRANTS[key]
def calculate_revision(revision,require_complete=False):
    template=AssessmentMatrixTemplate.from_dict(revision.matrix_template_snapshot) if revision.matrix_template_snapshot else get_template(revision.matrix_template_id)
    by_id={r.criterion_id:r for r in revision.criterion_results}; missing=[]
    for section in template.sections:
        for c in section.criteria:
            if c.id not in by_id: missing.append(c.name); continue
            try: score_result(by_id[c.id],template)
            except ValueError:
                if require_complete: raise
            if by_id[c.id].accepted_score is None: missing.append(c.name)
    if require_complete:
        if not revision.assessment_date: missing.append("Дата оценки")
        if not revision.inspector.strip(): missing.append("Инспектор")
        if missing: raise ValueError("Не заполнено: "+", ".join(missing))
    def total(section):
        values=[by_id[c.id].accepted_score for c in template.section(section).criteria if c.id in by_id]
        return None if len(values)!=len(template.section(section).criteria) or any(v is None for v in values) else sum(values)
    revision.design_achievement_points=total(DESIGN); revision.face_condition_points=total(CONDITION)
    revision.design_achievement_index=None if revision.design_achievement_points is None else revision.design_achievement_points/template.section(DESIGN).maximum_points
    revision.face_condition_index=None if revision.face_condition_points is None else revision.face_condition_points/template.section(CONDITION).maximum_points
    if revision.design_achievement_index is not None and revision.face_condition_index is not None: revision.result_quadrant,revision.result_label=classify(revision.design_achievement_index,revision.face_condition_index,template)
    else: revision.result_quadrant=revision.result_label=None
    return revision

class AssessmentAreaEvaluationService:
    def __init__(self,state): self.state=state
    def detect_template(self,area):
        confirmed={l.blast_event_id for l in area.event_links if l.status=="confirmed" and l.assessment_area_geometry_revision_id==area.active_geometry_revision_id}
        controlled=any(e.id in confirmed and e.event_type=="contour" for e in self.state.blast_events)
        return ("controlled_blasting_v1" if controlled else "no_controlled_blasting_v1",controlled,"confirmed_link" if controlled else "no_confirmed_contour_link")
    def new_evaluation(self,area,template_id=None,override_reason=None):
        if area.is_archived: raise ValueError("Архивная Assessment Area доступна только для чтения")
        detected,present,source=self.detect_template(area)
        if template_id and template_id!=detected and not (override_reason or "").strip(): raise ValueError("Для ручного выбора матрицы укажите причину")
        chosen=template_id or detected; template=get_template(chosen); eid=f"AAE-{uuid4()}"
        evaluation=AssessmentAreaEvaluation(eid,area.id); self.state.evaluations.append(evaluation)
        revision=AssessmentAreaEvaluationRevision("",eid,0,datetime.now(timezone.utc),date.today(),"","draft",area.active_geometry_revision_id,chosen,template.version,template.to_dict(),chosen=="controlled_blasting_v1","manual_override" if template_id and template_id!=detected else source,linked_event_snapshots=self.snapshot_links(area),change_reason=override_reason or "")
        return evaluation,revision
    def snapshot_links(self,area):
        result=[]
        for link in area.event_links:
            if link.status!="confirmed" or link.assessment_area_geometry_revision_id!=area.active_geometry_revision_id: continue
            event=next((e for e in self.state.blast_events if e.id==link.blast_event_id),None)
            if not event: continue
            card=next((c for c in self.state.technical_cards if c.blast_event_id==event.id),None); cardrev=card.active_revision() if card else None
            result.append(LinkedEventSnapshot(link.id,event.id,event.name,event.event_type,link.geometry_revision_id,cardrev.id if cardrev else None,event.elevation,event.event_type=="production",event.event_type=="contour"))
        return result
