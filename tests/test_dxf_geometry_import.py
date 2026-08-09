from pathlib import Path

import pytest

ezdxf = pytest.importorskip("ezdxf")

from prototype_2d.blast_geometry import build_contour_geometry, build_production_geometry
from prototype_2d.domain import AssessmentDomainState
from prototype_2d.dxf_importer import DxfImportError, import_dxf_polylines
from prototype_2d.line_geometry_importer import LineGeometryImportError, import_line_geometry
from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService


def save(tmp_path, build, name="geometry.dxf"):
    doc = ezdxf.new(); build(doc.modelspace()); path = tmp_path / name; doc.saveas(path); return path


def test_lwpolyline_wcs_metadata_elevation_and_closed_normalization(tmp_path):
    def build(msp):
        line = msp.add_lwpolyline([(0, 0), (10, 0), (10, 10)], dxfattribs={"layer": "BENCH", "elevation": 620})
        line.closed = True
    result = import_dxf_polylines(save(tmp_path, build))
    line = result.lines[0]
    assert [(p.x, p.y, p.z) for p in line.points] == [(0,0,620),(10,0,620),(10,10,620),(0,0,620)]
    assert line.source_type == line.assigned_type == "BENCH"
    assert line.is_horizontal and line.elevation == 620
    assert line.points[0].extra_values["dxf_entity_type"] == "LWPOLYLINE"
    assert result.summary.lwpolyline_count == 1 and result.summary.total_vertices == 4


def test_2d_and_3d_polyline_wcs_order_and_varying_z(tmp_path):
    def build(msp):
        msp.add_polyline2d([(1,2,610),(3,4,610)], dxfattribs={"layer":"2D", "elevation": 610})
        msp.add_polyline3d([(5,6,630),(7,8,614)], dxfattribs={"layer":"HOLES"})
    result = import_dxf_polylines(save(tmp_path, build))
    assert [(p.x,p.y,p.z) for p in result.lines[0].points] == [(1,2,610),(3,4,610)]
    assert result.lines[0].source_type == "2D" and result.lines[0].is_horizontal
    assert [(p.x,p.y,p.z) for p in result.lines[1].points] == [(5,6,630),(7,8,614)]
    assert not result.lines[1].is_horizontal
    assert result.summary.polyline_2d_count == result.summary.polyline_3d_count == 1


def test_explicitly_closed_polyline_is_not_closed_twice(tmp_path):
    path = save(tmp_path, lambda m: (lambda e: setattr(e, "closed", True))(m.add_lwpolyline([(0,0),(1,0),(0,0)])))
    assert len(import_dxf_polylines(path).lines[0].points) == 3


def test_bulge_is_rejected(tmp_path):
    path = save(tmp_path, lambda m: m.add_lwpolyline([(0,0,1),(1,0,0)], format="xyb"))
    with pytest.raises(DxfImportError, match="Curved DXF polyline"):
        import_dxf_polylines(path)


def test_project_lines_service_and_case_insensitive_dispatch(tmp_path):
    def build(msp):
        for z in (600,610,620): msp.add_lwpolyline([(0,z),(10,z)], dxfattribs={"elevation":z})
    path=save(tmp_path,build,"LINES.DXF"); state=AssessmentDomainState()
    dataset,_=ProjectLinesDatasetService(state).import_dataset(path)
    assert dataset.source_file_name == "LINES.DXF" and len(dataset.lines) == 3 and dataset.is_active
    assert ProjectLinesDatasetService(state).available_elevations() == [600,610,620]


def test_existing_builders_accept_normalized_dxf(tmp_path):
    def production(msp):
        for z in (620,630):
            line=msp.add_lwpolyline([(0,0),(10,0),(10,10)],dxfattribs={"elevation":z}); line.closed=True
    built=build_production_geometry(import_line_geometry(save(tmp_path,production)).lines)
    assert built.elevation == 630 and built.closed_polygon_count == 2 and built.multiple_polygons_warning
    def contour(msp):
        msp.add_polyline3d([(1,2,630),(1,2,615)])
        msp.add_polyline3d([(3,4,631),(3,4,614)])
        msp.add_lwpolyline([(8,8),(9,9)],dxfattribs={"elevation":620})
    result=build_contour_geometry(import_line_geometry(save(tmp_path,contour,"holes.dxf")).lines)
    assert [(p.x,p.y,p.z) for p in result.collar_points] == [(1,2,630),(3,4,631)]
    assert result.ignored_flat_line_count == 1


def test_unsupported_extension():
    with pytest.raises(LineGeometryImportError, match="Use .csv or .dxf"):
        import_line_geometry(Path("geometry.txt"))

