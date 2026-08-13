from datetime import datetime, timezone

import pytest

from domain.assessment.entities import AssessmentAreaGeometryRevision
from domain.assessment.geometry import (AssessmentBoundary, ProjectLineSpan, SpatialPoint, StraightConnector,
    derive_elevation_summary, derive_plan_polygon, extract_project_line_span, interpolate_anchor,
    snap_to_project_lines)
from domain.geometry.types import DatamineLine, DataminePoint, PlanPoint


def line(identity, points, order=0):
    return DatamineLine(identity,[DataminePoint(x,y,z,i+1) for i,(x,y,z) in enumerate(points)],import_order=order)

def anchor(dataset, source, segment, fraction): return interpolate_anchor(dataset,source,segment,fraction)

def rectangle():
    upper=line("upper",[(0,10,110),(5,10,112),(10,10,115)])
    lower=line("lower",[(0,0,100),(5,0,101),(10,0,102)])
    u0,u1=anchor("A",upper,0,0),anchor("A",upper,1,1)
    l0,l1=anchor("A",lower,1,1),anchor("A",lower,0,0)
    return AssessmentBoundary((extract_project_line_span(upper,u0,u1),StraightConnector(u1.frozen_point_xyz,l0.frozen_point_xyz,u1,l0),
       extract_project_line_span(lower,l0,l1),StraightConnector(l1.frozen_point_xyz,u0.frozen_point_xyz,l1,u0)))

def test_parallel_sloping_curved_and_round_trip_fixture():
    boundary=rectangle(); polygon=derive_plan_polygon(boundary)
    assert len(boundary.segments[0].frozen_trace_xyz)==3
    assert boundary.segments[0].frozen_trace_xyz[1]==SpatialPoint(5,10,112)
    assert derive_elevation_summary(boundary)==(100,115)
    assert AssessmentBoundary.from_dict(boundary.to_dict())==boundary
    revision=AssessmentAreaGeometryRevision("R1","A",1,datetime.now(timezone.utc),boundary,polygon,100,115)
    assert AssessmentAreaGeometryRevision.from_dict(revision.to_dict())==revision

def test_interpolation_forward_reverse_and_same_segment():
    source=line("curve",[(0,0,0),(2,2,10),(4,0,20),(6,2,30)])
    a,b=anchor("D",source,0,.5),anchor("D",source,2,.5)
    assert a.frozen_point_xyz==SpatialPoint(1,1,5)
    assert extract_project_line_span(source,a,b).frozen_trace_xyz==(SpatialPoint(1,1,5),SpatialPoint(2,2,10),SpatialPoint(4,0,20),SpatialPoint(5,1,25))
    assert extract_project_line_span(source,b,a).frozen_trace_xyz==tuple(reversed(extract_project_line_span(source,a,b).frozen_trace_xyz))
    c=anchor("D",source,0,.75)
    assert extract_project_line_span(source,a,c).frozen_trace_xyz==(SpatialPoint(1,1,5),SpatialPoint(1.5,1.5,7.5))

def test_deterministic_nearest_snap_and_tie_break():
    later=line("z",[(0,1,1),(10,1,1)],2); first=line("a",[(0,-1,2),(10,-1,2)],1)
    result=snap_to_project_lines(PlanPoint(5,0),"D",[later,first],2)
    assert result.anchor.source_line_id=="a" and result.anchor.source_segment_index==0

def test_interrupted_triangle_mixed_and_no_z():
    a,b,c=SpatialPoint(0,0),SpatialPoint(5,0),SpatialPoint(2,4)
    boundary=AssessmentBoundary((StraightConnector(a,b),StraightConnector(b,c),StraightConnector(c,a)))
    assert len(derive_plan_polygon(boundary).ring)==4
    assert derive_elevation_summary(boundary)==(None,None)

def test_continuity_and_self_intersection_rejected():
    a,b,c,d=map(lambda p: SpatialPoint(*p),[(0,0),(2,2),(0,2),(2,0)])
    with pytest.raises(ValueError,match="continuous"):
        AssessmentBoundary((StraightConnector(a,b),StraightConnector(c,d),StraightConnector(d,a)))
    with pytest.raises(ValueError):
        AssessmentBoundary((StraightConnector(a,b),StraightConnector(b,c),StraightConnector(c,d),StraightConnector(d,a)))

def test_frozen_dataset_a_is_unchanged_when_b_appears():
    boundary=rectangle(); frozen=boundary.to_dict(); _dataset_b=line("replacement",[(0,0,999),(1,1,999)])
    assert boundary.to_dict()==frozen and boundary.segments[0].start_anchor.source_dataset_id=="A"

def test_boundary_schema_and_frozen_provenance_invariants():
    source=line("L",[(0,0,100),(10,0,110)])
    start,end=anchor("D",source,0,0),anchor("D",source,0,1)
    with pytest.raises(ValueError,match="source IDs"):
        type(start)("", "L", 0, 0, start.frozen_point_xyz)
    with pytest.raises(ValueError,match="start"):
        ProjectLineSpan(start,end,(SpatialPoint(1,0,100),end.frozen_point_xyz))
    with pytest.raises(ValueError,match="non-zero"):
        StraightConnector(start.frozen_point_xyz,start.frozen_point_xyz,start,start)
    with pytest.raises(ValueError,match="does not match"):
        StraightConnector(start.frozen_point_xyz,SpatialPoint(1,1),None,end)
    with pytest.raises(ValueError,match="schema version"):
        AssessmentBoundary.from_dict({"version":2,"segments":[]})


@pytest.mark.parametrize("first_snapped,last_snapped",[(True,True),(True,False),(False,True),(False,False)])
def test_closing_connector_preserves_optional_endpoint_anchors(first_snapped,last_snapped):
    source=line("L",[(0,0,100),(10,0,110)])
    first_anchor=anchor("D",source,0,0) if first_snapped else None
    last_anchor=anchor("D",source,0,1) if last_snapped else None
    first=first_anchor.frozen_point_xyz if first_anchor else SpatialPoint(0,0)
    last=last_anchor.frozen_point_xyz if last_anchor else SpatialPoint(10,0)
    connector=StraightConnector(last,first,last_anchor,first_anchor)
    restored=StraightConnector(**{
        "start_point": SpatialPoint.from_dict(connector.to_dict()["start_point"]),
        "end_point": SpatialPoint.from_dict(connector.to_dict()["end_point"]),
        "start_anchor": type(last_anchor).from_dict(connector.to_dict()["start_anchor"]) if last_anchor else None,
        "end_anchor": type(first_anchor).from_dict(connector.to_dict()["end_anchor"]) if first_anchor else None})
    assert restored==connector
