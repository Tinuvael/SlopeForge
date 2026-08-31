from __future__ import annotations

from math import atan2, cos, pi, sin

import pytest

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.wall_conformance import SurfaceRoleMapping, build_transverse_profiles


MAPPING = SurfaceRoleMapping(
    "COLOUR", ((2, "face"), (5, "berm"), (3, "road"))
)


def _strip_surface(
    *,
    offset_x: float = 0.0,
    road_above: bool = False,
    multi_bench: bool = False,
) -> TriangleSurface:
    ys = (0.0, 10.0, 20.0)
    if multi_bench:
        xs = (-4.0, 0.0, 5.0, 7.0, 12.0, 14.0)
        zs = (30.0, 30.0, 20.0, 20.0, 10.0, 10.0)
        roles = (3, 2, 5, 2, 5)
    elif road_above:
        xs = (-4.0, 0.0, 10.0, 14.0)
        zs = (20.0, 20.0, 10.0, 10.0)
        roles = (3, 2, 5)
    else:
        xs = (-4.0, 0.0, 10.0, 14.0)
        zs = (20.0, 20.0, 10.0, 10.0)
        roles = (5, 2, 5)
    vertices = tuple(
        SurfaceVertex(offset_x + x, y, zs[column])
        for column, x in enumerate(xs)
        for y in ys
    )
    triangles = []
    for column, role in enumerate(roles):
        for row in range(len(ys) - 1):
            a = column * len(ys) + row
            b = a + 1
            c = (column + 1) * len(ys) + row
            d = c + 1
            triangles.extend((
                SurfaceTriangle((a, c, b), source_attributes={"COLOUR": role}),
                SurfaceTriangle((c, d, b), source_attributes={"COLOUR": role}),
            ))
    return TriangleSurface(vertices, tuple(triangles))


def _combine(*surfaces: TriangleSurface) -> TriangleSurface:
    vertices = []
    triangles = []
    for surface in surfaces:
        offset = len(vertices)
        vertices.extend(surface.vertices)
        triangles.extend(
            SurfaceTriangle(
                tuple(offset + index for index in triangle.vertex_indices),
                source_attributes=triangle.source_attributes,
            )
            for triangle in surface.triangles
        )
    return TriangleSurface(tuple(vertices), tuple(triangles))


def _area(upstream_x: float, downstream_x: float = 12.0) -> PlanPolygon:
    return PlanPolygon((
        PlanPoint(upstream_x, 1.25),
        PlanPoint(downstream_x, 1.25),
        PlanPoint(downstream_x, 18.4),
        PlanPoint(upstream_x, 18.4),
        PlanPoint(upstream_x, 1.25),
    ))


def _profile_signature(result):
    return tuple(
        (round(profile.alignment.origin.x, 6), round(profile.alignment.origin.y, 6))
        for profile in result.profiles
    )


def test_equivalent_wall_extent_is_independent_of_upstream_boundary_source() -> None:
    design = _strip_surface(road_above=True)
    crest_based = build_transverse_profiles(
        design, design, _area(0.0), MAPPING, spacing_m=3.0, tangent_window_m=3.0
    )
    road_and_straight_closure = build_transverse_profiles(
        design, design, _area(-3.0), MAPPING, spacing_m=3.0, tangent_window_m=3.0
    )

    assert _profile_signature(road_and_straight_closure) == _profile_signature(crest_based)
    assert all(profile.alignment.origin.x == pytest.approx(0.0) for profile in crest_based.profiles)


def test_crest_may_be_outside_when_descending_face_crosses_area() -> None:
    design = _strip_surface()
    result = build_transverse_profiles(
        design, design, _area(0.2, 8.0), MAPPING,
        spacing_m=3.0, tangent_window_m=3.0,
    )

    assert result.profiles
    assert all(profile.alignment.origin.x == pytest.approx(0.0) for profile in result.profiles)
    assert all(profile.assessment_u_interval[0] == pytest.approx(0.2) for profile in result.profiles)
    assert all(
        any(element.role == "face" for element in profile.design_section.elements)
        for profile in result.profiles
    )


def test_road_above_wall_is_context_not_alignment() -> None:
    design = _strip_surface(road_above=True)
    result = build_transverse_profiles(
        design, design, _area(-3.0, 8.0), MAPPING,
        spacing_m=4.0, tangent_window_m=3.0,
    )

    assert result.profiles
    assert all(profile.alignment.origin.x == pytest.approx(0.0) for profile in result.profiles)
    assert all(profile.alignment.origin.z == pytest.approx(20.0) for profile in result.profiles)
    assert all(
        profile.design_section.upstream_context is not None
        and profile.design_section.upstream_context.role == "road"
        for profile in result.profiles
    )


def _curved_wall(point_count: int = 33) -> TriangleSurface:
    angles = tuple((pi / 2.0) * index / (point_count - 1) for index in range(point_count))
    radii = (12.0, 10.0, 6.0, 4.0)
    elevations = (20.0, 20.0, 10.0, 10.0)
    vertices = tuple(
        SurfaceVertex(radius * cos(angle), radius * sin(angle), elevations[ring])
        for ring, radius in enumerate(radii)
        for angle in angles
    )
    triangles = []
    for ring, role in enumerate((5, 2, 5)):
        for index in range(point_count - 1):
            a = ring * point_count + index
            b = a + 1
            c = (ring + 1) * point_count + index
            d = c + 1
            triangles.extend((
                SurfaceTriangle((a, c, b), source_attributes={"COLOUR": role}),
                SurfaceTriangle((c, d, b), source_attributes={"COLOUR": role}),
            ))
    return TriangleSurface(vertices, tuple(triangles))


def _sector_area(start_angle: float, end_angle: float) -> PlanPolygon:
    outer = tuple(
        PlanPoint(9.7 * cos(start_angle + (end_angle - start_angle) * index / 12.0),
                  9.7 * sin(start_angle + (end_angle - start_angle) * index / 12.0))
        for index in range(13)
    )
    inner = tuple(
        PlanPoint(5.5 * cos(start_angle + (end_angle - start_angle) * index / 12.0),
                  5.5 * sin(start_angle + (end_angle - start_angle) * index / 12.0))
        for index in reversed(range(13))
    )
    return PlanPolygon((*outer, *inner, outer[0]))


def test_curved_area_adds_meaningful_start_and_end_stations_between_spacing() -> None:
    design = _curved_wall()
    start_angle, end_angle = 0.17, 1.19
    result = build_transverse_profiles(
        design, design, _sector_area(start_angle, end_angle), MAPPING,
        spacing_m=3.0, tangent_window_m=1.5,
    )

    angles = sorted(
        atan2(profile.alignment.origin.y, profile.alignment.origin.x)
        for profile in result.profiles
    )
    assert angles[0] == pytest.approx(start_angle, abs=0.01)
    assert angles[-1] == pytest.approx(end_angle, abs=0.01)
    assert angles[-1] - max(angle for angle in angles if angle < angles[-1]) < 0.31
    assert all(hypot_xy(profile.alignment.origin.x, profile.alignment.origin.y) == pytest.approx(10.0, abs=0.01)
               for profile in result.profiles)


def hypot_xy(x: float, y: float) -> float:
    return (x * x + y * y) ** 0.5


def test_internal_bench_crest_is_not_promoted_when_full_wall_is_assessed() -> None:
    design = _strip_surface(multi_bench=True)
    result = build_transverse_profiles(
        design, design, _area(0.2, 13.0), MAPPING,
        spacing_m=4.0, tangent_window_m=3.0,
    )

    assert result.profiles
    assert all(profile.alignment.origin.x == pytest.approx(0.0) for profile in result.profiles)
    assert all(all(point.x == pytest.approx(0.0) for point in line.points) for line in result.crest_lines)


def test_multiple_design_wall_components_inside_one_area_are_all_represented() -> None:
    design = _combine(_strip_surface(), _strip_surface(offset_x=25.0))
    area = PlanPolygon((
        PlanPoint(0.2, 1.25), PlanPoint(37.0, 1.25),
        PlanPoint(37.0, 18.4), PlanPoint(0.2, 18.4), PlanPoint(0.2, 1.25),
    ))
    result = build_transverse_profiles(
        design, design, area, MAPPING, spacing_m=4.0, tangent_window_m=3.0
    )

    assert len(result.crest_lines) == 2
    assert {round(profile.alignment.origin.x, 6) for profile in result.profiles} == {0.0, 25.0}
    assert {profile.alignment.boundary_component_index for profile in result.profiles} == {0, 1}


def test_small_upstream_boundary_perturbation_does_not_change_profile_topology() -> None:
    design = _strip_surface()
    just_inside = build_transverse_profiles(
        design, design, _area(-0.02), MAPPING, spacing_m=3.0, tangent_window_m=3.0
    )
    just_outside = build_transverse_profiles(
        design, design, _area(0.02), MAPPING, spacing_m=3.0, tangent_window_m=3.0
    )

    assert _profile_signature(just_outside) == _profile_signature(just_inside)
    assert len(just_outside.crest_lines) == len(just_inside.crest_lines) == 1
