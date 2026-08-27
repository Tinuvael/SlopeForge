from __future__ import annotations

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.wall_conformance import (
    SurfaceRoleMapping,
    WallTransitionLine,
    build_transverse_profiles,
    extract_design_wall_topology,
    sample_wall_alignment,
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
    profiles = build_transverse_profiles(
        surface, surface, _area(), MAPPING,
        spacing_m=5.0, tangent_window_m=4.0, half_width_m=40.0,
    )
    other_crests = [
        line
        for line in topology.transitions
        if line.kind == "crest" and line is not profiles.crest_line
    ]
    assert {point.x for point in profiles.crest_line.points} == {0.0}
    assert max(line.plan_length for line in other_crests) > profiles.crest_line.plan_length
    assert len(profiles.toe_lines) == 1
    assert {point.x for point in profiles.toe_lines[0].points} == {26.0}
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
    alignment = next(
        boundary
        for boundary in topology.alignment_boundaries
        if {point.x for point in boundary.line.points} == {0.0}
    )
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


def _connected_ramp_surface() -> TriangleSurface:
    """Road cells form one ramp corridor through multiple bench levels."""
    ys = (0.0, 7.0, 9.0, 11.0, 13.0, 20.0)
    xs = (0.0, 4.0, 9.0, 14.0, 21.0, 26.0, 31.0)
    base_z = (120.0, 101.0, 100.0, 84.0, 82.0, 70.0, 69.0)
    vertices = tuple(
        SurfaceVertex(x, y, base_z[column] + 0.18 * y)
        for column, x in enumerate(xs)
        for y in ys
    )
    triangles = []
    normal_roles = (2, 5, 2, 3, 2, 5)
    for column, normal_role in enumerate(normal_roles):
        for row in range(len(ys) - 1):
            # Between y=9 and y=11 the Road cuts through both the upper
            # platform and Face 2, joining the lower Road into one component.
            role = 3 if row == 2 and column in {1, 2, 3} else normal_role
            a = column * len(ys) + row
            b = a + 1
            c = (column + 1) * len(ys) + row
            d = c + 1
            triangles.extend((
                SurfaceTriangle((a, c, b), source_attributes={"COLOUR": role}),
                SurfaceTriangle((c, d, b), source_attributes={"COLOUR": role}),
            ))
    return TriangleSurface(vertices, tuple(triangles))


def test_connected_road_ramp_does_not_define_global_face_hierarchy():
    surface = _connected_ramp_surface()
    profiles = build_transverse_profiles(
        surface, surface, _area(), MAPPING,
        spacing_m=2.0, tangent_window_m=3.0, half_width_m=40.0,
    )
    assert {point.x for point in profiles.crest_line.points} == {0.0}
    assert profiles.profiles
    assert all(profile.alignment.normal_xy[0] > 0 for profile in profiles.profiles)
    signatures = {variant.signature for variant in profiles.design_variants}
    assert signatures == {
        "FACE-BERM-FACE-ROAD-FACE-BERM",
        "FACE-ROAD-FACE-BERM",
    }


def _folded_crest_surface() -> TriangleSurface:
    crest_xy = ((0.0, 0.0), (0.0, 10.0), (10.0, 10.0),
                (10.0, 0.0), (2.0, 0.0))
    inward = ((1.0, 0.0), (0.7, -0.7), (-0.7, -0.7),
              (-0.7, 0.7), (0.0, 1.0))
    vertices = []
    for (x, y), (nx, ny) in zip(crest_xy, inward):
        vertices.extend((
            SurfaceVertex(x - nx * 3.0, y - ny * 3.0, 20.0),
            SurfaceVertex(x, y, 20.0),
            SurfaceVertex(x + nx * 3.0, y + ny * 3.0, 10.0),
            SurfaceVertex(x + nx * 6.0, y + ny * 6.0, 10.0),
        ))
    triangles = []
    for row in range(len(crest_xy) - 1):
        first, second = row * 4, (row + 1) * 4
        for offset, role in ((0, 5), (1, 2), (2, 3)):
            a, b = first + offset, second + offset
            c, d = a + 1, b + 1
            triangles.extend((
                SurfaceTriangle((a, c, b), source_attributes={"COLOUR": role}),
                SurfaceTriangle((c, d, b), source_attributes={"COLOUR": role}),
            ))
    return TriangleSurface(tuple(vertices), tuple(triangles))


def test_folded_upper_crest_extra_crossing_does_not_replace_profile_origin():
    surface = _folded_crest_surface()
    area = PlanPolygon((
        PlanPoint(-4, -4), PlanPoint(14, -4), PlanPoint(14, 14),
        PlanPoint(-4, 14), PlanPoint(-4, -4),
    ))
    result = build_transverse_profiles(
        surface, surface, area, MAPPING,
        spacing_m=4.0, tangent_window_m=3.0, half_width_m=14.0,
    )
    assert result.profiles
    folded_profiles = [
        profile
        for profile in result.profiles
        if abs(profile.alignment.origin.x) < 1e-6
        and 0.0 < profile.alignment.origin.y < 10.0
    ]
    assert folded_profiles
    assert any(
        sum(
            1
            for first, second in zip(
                result.crest_line.points, result.crest_line.points[1:]
            )
            if (
                profile.alignment.normal_xy[0]
                * (first.y - profile.alignment.origin.y)
                - profile.alignment.normal_xy[1]
                * (first.x - profile.alignment.origin.x)
            )
            * (
                profile.alignment.normal_xy[0]
                * (second.y - profile.alignment.origin.y)
                - profile.alignment.normal_xy[1]
                * (second.x - profile.alignment.origin.x)
            )
            <= 1e-9
        )
        >= 2
        for profile in folded_profiles
    )
    assert any(
        abs(profile.alignment.origin.x) < 1e-6
        and 0.0 < profile.alignment.origin.y < 10.0
        for profile in result.profiles
    )
    assert all(
        any(
            abs(point.u) < 1e-6
            for segment in profile.design_segments
            for point in (segment.start, segment.end)
        )
        for profile in result.profiles
    )
