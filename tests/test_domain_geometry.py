from pathlib import Path
import pytest
from prototype_2d.domain import PlanPoint
from prototype_2d.domain_geometry import DomainGeometryValidationError,build_domain_polygons
from prototype_2d.line_geometry_importer import import_line_geometry
from prototype_2d.models import DatamineLine,DataminePoint

def line(points,identifier="L",order=0):
    return DatamineLine(identifier,[DataminePoint(x,y,z,i) for i,(x,y,z) in enumerate(points)],import_order=order)

def test_horizontal_and_non_planar_xy_projection_are_closed_without_mutation():
    horizontal=line([(0,0,10),(2,0,10),(2,2,10),(0,0,10)])
    nonplanar=line([(10,10,630),(12,10,610),(12,12,590),(10.01,10.01,580)])
    original=nonplanar.to_dict(); result=build_domain_polygons([horizontal,nonplanar])
    assert len(result.polygons)==2
    assert result.polygons[0].ring==(PlanPoint(0,0),PlanPoint(2,0),PlanPoint(2,2),PlanPoint(0,0))
    assert result.polygons[1].ring[-1]==PlanPoint(10,10)
    assert nonplanar.to_dict()==original

def test_xy_closed_with_different_endpoint_z_is_valid():
    result=build_domain_polygons([line([(0,0,630),(4,0,620),(0,4,610),(0,0,600)])])
    assert len(result.polygons)==1

def test_multiple_order_open_and_degenerate_summary():
    a=line([(0,0,0),(1,0,0),(0,1,0),(0,0,5)],"A",2)
    b=line([(2,2,0),(3,2,1),(2,3,2),(2,2,3)],"B",1)
    opened=line([(0,0,0),(1,0,0),(1,1,0)],"open")
    vertical=line([(9,9,3),(9,9,2),(9,9,1),(9,9,0)],"vertical")
    result=build_domain_polygons([a,b,opened,vertical])
    assert len(result.polygons)==2 and result.skipped_open_lines==1 and result.skipped_degenerate_lines==1
    assert result.polygons[0].ring[0]==PlanPoint(0,0)

def test_no_valid_polygons_is_clear_error():
    with pytest.raises(DomainGeometryValidationError,match="No valid closed Domain polygons"):
        build_domain_polygons([line([(0,0,0),(1,0,0)])])

def test_real_csv_importer_projects_two_sid_lines(tmp_path):
    path=tmp_path/'domains.csv'; path.write_text('X,Y,Z,SID\n0,0,10,A\n2,0,11,A\n0,2,12,A\n0,0,9,A\n10,10,3,B\n12,10,4,B\n10,12,5,B\n10,10,1,B\n')
    result=build_domain_polygons(import_line_geometry(path).lines)
    assert len(result.polygons)==2

def test_real_dxf_importer_projects_2d_and_nonplanar_3d(tmp_path):
    import ezdxf
    doc=ezdxf.new(); msp=doc.modelspace(); msp.add_lwpolyline([(0,0),(2,0),(0,2)],close=True)
    poly=msp.add_polyline3d([(10,10,10),(12,10,20),(10,12,30),(10,10,1)]); poly.close()
    path=tmp_path/'domains.dxf'; doc.saveas(path)
    result=build_domain_polygons(import_line_geometry(path).lines)
    assert len(result.polygons)==2

def test_self_intersecting_import_is_skipped_but_valid_peer_survives():
    valid=line([(0,0,0),(4,0,0),(4,4,0),(0,4,0),(0,0,9)],"valid")
    bow_tie=line([(10,10,0),(14,14,1),(10,13,2),(13,10,3),(10,10,4)],"bow")
    result=build_domain_polygons([valid,bow_tie])
    assert len(result.polygons)==1
    assert result.polygons[0].ring[0]==PlanPoint(0,0)
    assert result.skipped_degenerate_lines==1


def test_all_self_intersecting_import_keeps_clear_validation_error():
    bow_tie=line([(0,0,0),(4,4,1),(0,3,2),(3,0,3),(0,0,4)])
    with pytest.raises(DomainGeometryValidationError,match="No valid closed Domain polygons"):
        build_domain_polygons([bow_tie])


@pytest.mark.parametrize("bad_value",[float("nan"),float("inf"),float("-inf")])
def test_non_finite_xy_is_skipped_while_valid_polygon_survives(bad_value):
    invalid=line([(0,0,0),(bad_value,0,0),(1,1,0),(0,0,0)],"invalid")
    valid=line([(10,10,0),(12,10,0),(10,12,0),(10,10,0)],"valid")
    result=build_domain_polygons([invalid,valid])
    assert result.polygons[0].ring[0]==PlanPoint(10,10)
    assert len(result.polygons)==1 and result.skipped_degenerate_lines==1


@pytest.mark.parametrize("bad_value",[float("nan"),float("inf"),float("-inf")])
def test_all_non_finite_xy_keeps_clear_validation_error(bad_value):
    invalid=line([(0,0,0),(1,bad_value,0),(1,1,0),(0,0,0)])
    with pytest.raises(DomainGeometryValidationError,match="No valid closed Domain polygons"):
        build_domain_polygons([invalid])
