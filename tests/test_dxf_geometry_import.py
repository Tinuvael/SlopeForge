from pathlib import Path

import ezdxf
import pytest
from ezdxf.lldxf.const import (
    POLYLINE_CURVE_FIT_VERTICES_ADDED,
    POLYLINE_SPLINE_FIT_VERTICES_ADDED,
)

from domain.geometry.blast import build_contour_geometry, build_production_geometry
from domain.geometry.types import PlanPoint
from domain.project.domain_geometry import build_domain_polygons
from application.state.assessment_domain_state import AssessmentDomainState
from infrastructure.geometry_import.dxf import DxfImportError, import_dxf_polylines
from infrastructure.geometry_import.lines import LineGeometryImportError, import_line_geometry
from application.services.project_lines import (
    ProjectLinesDatasetService,
    ProjectLinesImportError,
)


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
    from domain.assessment.geometry import project_line_is_closed
    assert project_line_is_closed(line)


def test_2d_and_3d_polyline_wcs_order_and_varying_z(tmp_path):
    def build(msp):
        # POLYLINE elevation is a DXF point (group codes 10/20/30), not a
        # scalar.  ezdxf 1.4 validates that representation when constructing
        # the test entity.
        msp.add_polyline2d([(1,2),(3,4)], dxfattribs={"layer":"2D", "elevation": (0, 0, 610)})
        msp.add_polyline3d([(5,6,630),(7,8,614)], dxfattribs={"layer":"HOLES"})
    result = import_dxf_polylines(save(tmp_path, build))
    assert [(p.x,p.y,p.z) for p in result.lines[0].points] == [(1,2,610),(3,4,610)]
    assert result.lines[0].source_type == "2D" and result.lines[0].is_horizontal
    assert [(p.x,p.y,p.z) for p in result.lines[1].points] == [(5,6,630),(7,8,614)]
    assert not result.lines[1].is_horizontal
    assert result.summary.polyline_2d_count == result.summary.polyline_3d_count == 1


def test_closed_legacy_3d_polyline_preserves_implicit_xyz_closing_segment(tmp_path):
    def build(msp):
        line = msp.add_polyline3d(
            [(0, 0, 630), (4, 0, 620), (0, 4, 610), (0, 0, 600)]
        )
        line.close()

    imported = import_dxf_polylines(save(tmp_path, build, "closed-3d.dxf"))

    assert [(point.x, point.y, point.z) for point in imported.lines[0].points] == [
        (0, 0, 630),
        (4, 0, 620),
        (0, 4, 610),
        (0, 0, 600),
        (0, 0, 630),
    ]
    assert imported.summary.total_vertices == 5

    domain = build_domain_polygons(imported.lines)
    assert domain.polygons[0].ring == (
        PlanPoint(0, 0), PlanPoint(4, 0), PlanPoint(0, 4), PlanPoint(0, 0)
    )

    production = build_production_geometry(imported.lines)
    assert production.plan_geometry.ring == (
        PlanPoint(0, 0), PlanPoint(4, 0), PlanPoint(0, 4), PlanPoint(0, 0)
    )


def test_explicitly_closed_polyline_is_not_closed_twice(tmp_path):
    path = save(tmp_path, lambda m: (lambda e: setattr(e, "closed", True))(m.add_lwpolyline([(0,0),(1,0),(0,0)])))
    assert len(import_dxf_polylines(path).lines[0].points) == 3


def test_bulge_is_rejected(tmp_path):
    path = save(tmp_path, lambda m: m.add_lwpolyline([(0,0,1),(1,0,0)], format="xyb"))
    with pytest.raises(DxfImportError, match="Curved DXF polyline"):
        import_dxf_polylines(path)


def test_legacy_2d_polyline_bulge_is_rejected(tmp_path):
    def build(msp):
        line = msp.add_polyline2d([(0, 0), (1, 0)])
        line.vertices[0].dxf.bulge = 1
    with pytest.raises(DxfImportError, match="Curved DXF polyline"):
        import_dxf_polylines(save(tmp_path, build, "curved-2d.dxf"))


@pytest.mark.parametrize(
    ("fit_flag", "name"),
    [
        (POLYLINE_CURVE_FIT_VERTICES_ADDED, "curve-fit-2d.dxf"),
        (POLYLINE_SPLINE_FIT_VERTICES_ADDED, "spline-fit-2d.dxf"),
    ],
)
def test_legacy_2d_polyline_fit_flags_are_rejected(tmp_path, fit_flag, name):
    def build(msp):
        line = msp.add_polyline2d([(0, 0), (1, 0), (1, 1)])
        line.dxf.flags |= fit_flag
    with pytest.raises(DxfImportError, match="Curved DXF polyline"):
        import_dxf_polylines(save(tmp_path, build, name))


def test_legacy_3d_polyline_curve_fit_flag_is_rejected(tmp_path):
    def build(msp):
        line = msp.add_polyline3d([(0, 0, 10), (1, 0, 9), (1, 1, 8)])
        line.dxf.flags |= POLYLINE_CURVE_FIT_VERTICES_ADDED
    with pytest.raises(DxfImportError, match="Curved DXF polyline"):
        import_dxf_polylines(save(tmp_path, build, "curve-fit-3d.dxf"))


def test_polygon_mesh_and_polyface_are_skipped(tmp_path):
    def build(msp):
        mesh = msp.add_polymesh((2, 2))
        mesh.set_mesh_vertex((0, 0), (0, 0, 0))
        polyface = msp.add_polyface()
        polyface.append_face([(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    result = import_dxf_polylines(save(tmp_path, build, "unsupported-polylines.dxf"))
    assert result.lines == []
    assert result.summary.skipped_unsupported_entity_count == 2


def test_supported_polyline_imports_alongside_unsupported_entity(tmp_path):
    def build(msp):
        msp.add_line((0, 0), (1, 1))
        msp.add_lwpolyline([(0, 0), (2, 0)], dxfattribs={"elevation": 610})
    result = import_dxf_polylines(save(tmp_path, build, "mixed.dxf"))
    assert len(result.lines) == 1
    assert result.lines[0].is_horizontal
    assert result.summary.skipped_unsupported_entity_count == 1


def test_project_lines_rejects_dxf_with_only_unsupported_entities(tmp_path):
    path = save(tmp_path, lambda msp: msp.add_line((0, 0), (1, 1)), "empty.dxf")
    state = AssessmentDomainState()
    with pytest.raises(ProjectLinesImportError, match="no suitable lines"):
        ProjectLinesDatasetService(state).import_dataset(path)
    assert state.datasets == []


@pytest.mark.parametrize("vertices", [[], [(0, 0)]], ids=["zero-vertices", "one-vertex"])
def test_project_lines_rejects_degenerate_supported_polylines(tmp_path, vertices):
    path = save(
        tmp_path,
        lambda msp: msp.add_lwpolyline(vertices, dxfattribs={"elevation": 610}),
        "degenerate.dxf",
    )
    state = AssessmentDomainState()
    with pytest.raises(ProjectLinesImportError, match="no suitable lines"):
        ProjectLinesDatasetService(state).import_dataset(path)
    assert state.datasets == []


def test_project_lines_mixed_dxf_persists_only_drawable_lines(tmp_path):
    def build(msp):
        msp.add_lwpolyline([(0, 0)], dxfattribs={"elevation": 600})
        msp.add_lwpolyline([(0, 0), (2, 0)], dxfattribs={"elevation": 610})
    state = AssessmentDomainState()
    dataset, result = ProjectLinesDatasetService(state).import_dataset(
        save(tmp_path, build, "mixed-project-lines.dxf")
    )
    assert len(result.lines) == 2
    assert len(dataset.lines) == 1
    assert len(dataset.lines[0].points) == 2


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


def test_csv_and_dxf_production_geometry_are_equivalent(tmp_path):
    csv_path = tmp_path / "block.csv"
    csv_path.write_text(
        "X,Y,Z,SID,PTN\n0,0,630,BLOCK,1\n10,0,630,BLOCK,2\n"
        "10,10,630,BLOCK,3\n0,0,630,BLOCK,4\n",
        encoding="utf-8",
    )
    def build(msp):
        line = msp.add_lwpolyline([(0, 0), (10, 0), (10, 10)], dxfattribs={"elevation": 630})
        line.closed = True
    dxf_path = save(tmp_path, build, "block.dxf")
    csv_geometry = build_production_geometry(import_line_geometry(csv_path).lines)
    dxf_geometry = build_production_geometry(import_line_geometry(dxf_path).lines)
    csv_xy = [(point.x, point.y) for point in csv_geometry.plan_geometry.ring]
    dxf_xy = [(point.x, point.y) for point in dxf_geometry.plan_geometry.ring]
    assert dxf_xy == csv_xy
    assert dxf_geometry.elevation == csv_geometry.elevation == 630
    assert dxf_xy[0] == dxf_xy[-1] and len(dxf_xy) == len(csv_xy) == 4


def test_unsupported_extension():
    with pytest.raises(LineGeometryImportError, match="Use .csv or .dxf"):
        import_line_geometry(Path("geometry.txt"))
