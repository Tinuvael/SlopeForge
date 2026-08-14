from datetime import date, datetime, timezone
import json

from application.services.assessment_areas import AssessmentAreaService
from application.services.assessment_event_links import AssessmentEventLinkService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.geometry.operations import (clip_datamine_line_by_polygon, point_in_polygon,
    polygon_area, polygon_self_intersects, segment_intersection)
from domain.blasting.entities import BlastEvent
from domain.geometry.types import (DatamineLine, DataminePoint, PlanLineString, PlanMultiPoint,
                                   PlanPoint, PlanPolygon)
from domain.project.project_lines import ProjectLinesDataset
from tests.assessment_boundary_fixtures import boundary_from_polygon


def polygon(*coordinates):
    points=tuple(PlanPoint(*item) for item in coordinates)
    return PlanPolygon(points+(points[0],))

def line(source_id,elevation,*coordinates):
    return DatamineLine(source_id,[DataminePoint(x,y,elevation,i) for i,(x,y) in enumerate(coordinates)])

def test_basic_polygon_operations_and_clipping():
    square=polygon((0,0),(10,0),(10,10),(0,10))
    assert polygon_area(square)==100 and point_in_polygon(PlanPoint(0,5),square)
    assert segment_intersection(PlanPoint(-1,5),PlanPoint(11,5),PlanPoint(0,0),PlanPoint(0,10))==PlanPoint(0,5)
    assert polygon_self_intersects(polygon((0,0),(10,10),(0,10),(10,0)))
    concave=polygon((0,0),(10,0),(10,10),(7,10),(7,3),(3,3),(3,10),(0,10))
    fragments=clip_datamine_line_by_polygon(line("L",100,(-2,5),(12,5)),concave)
    assert fragments==[PlanLineString((PlanPoint(0,5),PlanPoint(3,5))),PlanLineString((PlanPoint(7,5),PlanPoint(10,5)))]

def test_area_boundary_round_trip_archive_and_revision_history():
    shape=polygon((0,0),(10,0),(10,10),(0,10))
    dataset=ProjectLinesDataset("D-001","Main",datetime.now(timezone.utc),"a.csv",True,[line("L1",100,(0,0),(10,0))])
    state=AssessmentDomainState(datasets=[dataset]); service=AssessmentAreaService(state)
    first_boundary=boundary_from_polygon(shape,dataset_id="D-001",line_id="L1")
    area=service.create_area(name="A",assessment_date=date.today(),boundary=first_boundary)
    frozen=json.loads(json.dumps(area.geometry_revisions[0].to_dict()))
    second=polygon((1,0),(9,0),(9,10),(1,10))
    service.revise_area(area,boundary=boundary_from_polygon(second,dataset_id="D-001",line_id="L1"))
    assert area.active_geometry_revision().revision_number==2
    assert area.geometry_revisions[0].to_dict()==frozen
    area.archive("done")
    restored=AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.assessment_areas[0].to_dict()==area.to_dict()


def test_link_preview_is_non_mutating_and_uses_authoritative_matcher():
    shape = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    boundary = boundary_from_polygon(shape, minimum=600, maximum=630)
    production = BlastEvent("E-P", "Production 625", "production", date.today(), 625)
    production.add_geometry_revision(source_file_name="p.csv", source_geometry=[],
                                     plan_geometry=polygon((2, 2), (8, 2), (8, 8), (2, 8)), elevation=625)
    contour = BlastEvent("E-C", "Contour 630", "contour", date.today(), 630)
    contour.add_geometry_revision(source_file_name="c.csv", source_geometry=[],
                                  plan_geometry=PlanMultiPoint((PlanPoint(10.05, 5),)), elevation=630)
    state = AssessmentDomainState(blast_events=[production, contour])
    before = json.loads(json.dumps(state.to_dict()))

    preview = AssessmentEventLinkService(state).preview(boundary)

    assert (preview.total, preview.production_count, preview.contour_count) == (2, 1, 1)
    assert {item.blast_event_id for item in preview.items} == {"E-P", "E-C"}
    assert state.to_dict() == before and state.assessment_areas == []
