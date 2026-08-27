from __future__ import annotations

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.wall_conformance import (
    SurfaceRoleMapping,
    WallTransitionLine,
    build_transverse_profiles,
    extract_design_wall_topology,
    sample_wall_alignment,
    select_design_alignment,
)


MAPPING = SurfaceRoleMapping(
    "COLOUR", ((2, "face"), (5, "berm"), (3, "road"))
)


def _multi_face_surface(*, reverse_winding: bool = False) -> TriangleSurface:
    # Rows run along chainage. Columns run down-wall and deliberately contain
    # Face -> Berm -> Face -> Road -> Face -> lower Berm geometry.
    ys = (0.0, 10.0, 20.0)
    xs = (
        (0.0, 0.0, 0.0),
        (4.0, 4.0, 4.0),
        (9.0, 11.0, 9.0),  # longer intermediate crest than the upper rim
        (14.0, 14.0, 14.0),
        (21.0, 23.0, 21.0),
        (26.0, 26.0, 26.0),
        (31.0, 31.0, 31.0),
    )
    base_z = (120.0, 101.0, 100.0, 84.0, 82.0, 70.0, 69.0)
    grade = (0.0, -6.0, 7.0)
    vertices = tuple(
        SurfaceVertex(xs[column][row], y, base_z[column] + grade[row])
        for column in range(len(xs))
        for row, y in enumerate(ys)
    )
    roles = (2, 5, 2, 3, 2, 5)
    triangles = []
    for column, role in enumerate(roles):
        for row in range(len(ys) - 1):
            a = column * 3 + row
            b = a + 1
            c = (column + 1) * 3 + row
            d = c + 1
            indices = ((a, c, b), (c, d, b))
            for triangle in indices:
                if reverse_winding:
                    triangle = tuple(reversed(triangle))
                triangles.append(
                    SurfaceTriangle(
                        triangle, source_attributes={"COLOUR": role}
                    )
                )
    return TriangleSurface(vertices, tuple(triangles))


def _area() -> PlanPolygon:
    return PlanPolygon(
        (
            PlanPoint(-1, 1), PlanPoint(32, 1), PlanPoint(32, 19),
            PlanPoint(-1, 19), PlanPoint(-1, 1),
        )
    )


def test_alignment_uses_upper_face_patch_not_longest_intermediate_crest():
    surface = _multi_face_surface()
    topology = extract_design_wall_topology(surface, MAPPING)
    alignment = select_design_alignment(topology, _area())
    other_crests = [
        line for line in topology.transitions
        if line.kind == "crest" and line is not alignment.line
    ]

    assert {point.x for point in alignment.line.points} == {0.0}
    assert max(line.plan_length for line in other_crests) > alignment.line.plan_length

    profiles = build_transverse_profiles(
        surface, surface, _area(), MAPPING,
        spacing_m=5.0, tangent_window_m=4.0, half_width_m=40.0,
    )
    assert profiles.profiles
    assert all(profile.alignment.normal_xy[0] > 0 for profile in profiles.profiles)
    assert {profile.design_section.topology_signature for profile in profiles.profiles} == {
        "FACE-BERM-FACE-ROAD-FACE-BERM"
    }
    assert [variant.signature for variant in profiles.design_variants] == [
        "FACE-BERM-FACE-ROAD-FACE-BERM"
    ]


def test_face_patch_orientation_does_not_depend_on_triangle_winding():
    for reverse_winding in (False, True):
        profiles = build_transverse_profiles(
            _multi_face_surface(reverse_winding=reverse_winding),
            _multi_face_surface(reverse_winding=reverse_winding),
            _area(), MAPPING,
            spacing_m=7.0, tangent_window_m=4.0, half_width_m=40.0,
        )
        assert profiles.profiles
        assert all(profile.alignment.normal_xy[0] > 0 for profile in profiles.profiles)


def test_adjacent_face_patch_overrides_a_nearby_unrelated_toe():
    topology = extract_design_wall_topology(_multi_face_surface(), MAPPING)
    alignment = select_design_alignment(topology, _area())
    wrong_side_toe = WallTransitionLine(
        "toe",
        (SurfaceVertex(-0.1, 0, 0), SurfaceVertex(-0.1, 20, 0)),
    )
    samples = sample_wall_alignment(
        alignment.line,
        (wrong_side_toe,),
        _area(),
        spacing_m=7.0,
        tangent_window_m=4.0,
        interior_points=alignment.interior_points,
    )
    assert samples
    assert all(sample.normal_xy[0] > 0 for sample in samples)
