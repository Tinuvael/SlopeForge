from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.wall_conformance import (
    SurfaceRoleMapping, build_transverse_profiles, extract_design_transition_lines,
)


MAPPING = SurfaceRoleMapping("COLOUR", ((2, "face"), (3, "road")))


def _triangle(indices, role):
    return SurfaceTriangle(indices, source_attributes={"COLOUR": role})


def _uppermost_bench():
    vertices = (
        SurfaceVertex(0, 0, 10), SurfaceVertex(0, 20, 10),
        SurfaceVertex(5, 0, 0), SurfaceVertex(5, 20, 0),
        SurfaceVertex(10, 0, 0), SurfaceVertex(10, 20, 0),
    )
    triangles = (
        _triangle((0, 2, 1), 2), _triangle((2, 3, 1), 2),
        _triangle((2, 4, 3), 3), _triangle((4, 5, 3), 3),
    )
    return TriangleSurface(vertices, triangles)


def test_uppermost_face_boundary_is_crest_and_normal_toe_is_preserved():
    surface = _uppermost_bench()
    transitions = extract_design_transition_lines(surface, MAPPING)
    crest = next(line for line in transitions if line.kind == "crest")
    toe = next(line for line in transitions if line.kind == "toe")
    assert {(p.x, p.z) for p in crest.points} == {(0, 10)}
    assert {(p.x, p.z) for p in toe.points} == {(5, 0)}

    area = PlanPolygon((
        PlanPoint(-1, 3), PlanPoint(8, 3), PlanPoint(8, 17),
        PlanPoint(-1, 17), PlanPoint(-1, 3),
    ))
    result = build_transverse_profiles(
        surface, surface, area, MAPPING,
        spacing_m=5, tangent_window_m=4, half_width_m=12,
    )
    assert result.profiles
    assert all(profile.alignment.normal_xy[0] > 0 for profile in result.profiles)


def test_sloping_lateral_face_boundaries_are_not_crest_candidates():
    transitions = extract_design_transition_lines(_uppermost_bench(), MAPPING)
    crests = [line for line in transitions if line.kind == "crest"]
    crest_edges = {
        ((a.x, a.y, a.z), (b.x, b.y, b.z))
        for line in crests for a, b in zip(line.points, line.points[1:])
    }
    assert all(a[2] == b[2] == 10 for a, b in crest_edges)
