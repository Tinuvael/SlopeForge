from __future__ import annotations

from math import hypot

import pytest

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.wall_conformance import (
    SurfaceRoleMapping,
    WallAlignment,
    build_alignment_profile_sections,
    place_profiles_from_alignment,
)


ROLE_MAPPING = SurfaceRoleMapping(
    "material",
    (("face", "face"), ("berm", "berm"), ("road", "road")),
)


def _polygon(*points: tuple[float, float]) -> PlanPolygon:
    ring = tuple(PlanPoint(*point) for point in points)
    if ring[0] != ring[-1]:
        ring = (*ring, ring[0])
    return PlanPolygon(ring)


def _strip_surface(
    stations: tuple[tuple[float, float, tuple[float, float]], ...],
    cross_sections: tuple[tuple[float, float], ...],
    roles: tuple[str, ...],
) -> TriangleSurface:
    vertices: list[SurfaceVertex] = []
    rows: list[tuple[int, ...]] = []
    for x, y, normal in stations:
        row = []
        for offset, elevation in cross_sections:
            row.append(len(vertices))
            vertices.append(SurfaceVertex(
                x + normal[0] * offset,
                y + normal[1] * offset,
                elevation,
            ))
        rows.append(tuple(row))
    triangles: list[SurfaceTriangle] = []
    for station_index, (first, second) in enumerate(zip(rows, rows[1:])):
        for band_index, role in enumerate(roles):
            a, b = first[band_index], first[band_index + 1]
            c, d = second[band_index], second[band_index + 1]
            triangles.extend((
                SurfaceTriangle(
                    (a, b, c),
                    source_id=f"{role}-{station_index}-{band_index}-a",
                    source_attributes={"material": role},
                ),
                SurfaceTriangle(
                    (b, d, c),
                    source_id=f"{role}-{station_index}-{band_index}-b",
                    source_attributes={"material": role},
                ),
            ))
    return TriangleSurface(tuple(vertices), tuple(triangles))


def _straight_surface(*, actual_offset: float = 0.0) -> TriangleSurface:
    stations = (
        (0.0, 0.0, (0.0, 1.0)),
        (12.0, 0.0, (0.0, 1.0)),
    )
    sections = (
        (-2.0, 20.0 + actual_offset),
        (0.0, 20.0 + actual_offset),
        (4.0, 10.0 + actual_offset),
        (7.0, 10.0 + actual_offset),
        (11.0, 0.0 + actual_offset),
    )
    return _strip_surface(
        stations,
        sections,
        ("berm", "face", "berm", "face"),
    )


def _straight_alignment(*, reverse: bool = False) -> WallAlignment:
    points = (
        PlanPoint(0.0, 2.0),
        PlanPoint(0.0, 2.0),  # duplicate input is intentionally harmless
        PlanPoint(12.0, 2.0),
    )
    return WallAlignment(tuple(reversed(points)) if reverse else points)


def _assessment() -> PlanPolygon:
    return _polygon((-1.0, -1.0), (13.0, -1.0), (13.0, 12.0), (-1.0, 12.0))


def _placement_signature(result):
    return tuple(sorted(
        (
            round(item.alignment_point.x, 8),
            round(item.alignment_point.y, 8),
            round(item.downwall_xy[0], 8),
            round(item.downwall_xy[1], 8),
        )
        for item in result.placements
    ))


def test_straight_alignment_stations_by_true_chainage_at_bounded_spacing() -> None:
    result = place_profiles_from_alignment(
        alignment=_straight_alignment(),
        design_surface=_straight_surface(),
        assessment_polygon=_assessment(),
        role_mapping=ROLE_MAPPING,
        spacing_m=3.0,
    )

    assert result.supported
    assert result.diagnostics == ()
    assert result.station_chainages_m == pytest.approx((0.0, 3.0, 6.0, 9.0, 12.0))
    assert max(
        second - first
        for first, second in zip(
            result.station_chainages_m, result.station_chainages_m[1:]
        )
    ) <= 3.0
    for placement in result.placements:
        assert placement.downwall_xy == pytest.approx((0.0, 1.0))
        assert placement.tangent_xy[0] * placement.downwall_xy[0] + (
            placement.tangent_xy[1] * placement.downwall_xy[1]
        ) == pytest.approx(0.0)


def _curved_fixture() -> tuple[TriangleSurface, WallAlignment, PlanPolygon]:
    centers = (
        (0.0, 0.0),
        (5.0, 0.4),
        (10.0, 1.5),
        (15.0, 3.2),
        (20.0, 5.5),
    )
    stations = []
    normals = []
    for index, point in enumerate(centers):
        previous = centers[max(0, index - 1)]
        following = centers[min(len(centers) - 1, index + 1)]
        tangent = following[0] - previous[0], following[1] - previous[1]
        length = hypot(*tangent)
        tangent = tangent[0] / length, tangent[1] / length
        normal = -tangent[1], tangent[0]
        normals.append(normal)
        stations.append((point[0], point[1], normal))
    surface = _strip_surface(
        tuple(stations),
        ((-2.0, 20.0), (0.0, 20.0), (4.0, 10.0), (8.0, 10.0)),
        ("berm", "face", "berm"),
    )
    alignment = WallAlignment(tuple(
        PlanPoint(x + normal[0] * 2.0, y + normal[1] * 2.0)
        for (x, y), normal in zip(centers, normals)
    ))
    upper = tuple(
        PlanPoint(x + normal[0] * -1.0, y + normal[1] * -1.0)
        for (x, y), normal in zip(centers, normals)
    )
    lower = tuple(
        PlanPoint(x + normal[0] * 7.0, y + normal[1] * 7.0)
        for (x, y), normal in zip(centers, normals)
    )
    assessment = PlanPolygon((*upper, *reversed(lower), upper[0]))
    return surface, alignment, assessment


def test_curved_alignment_rotates_smoothly_without_downwall_sign_flips() -> None:
    surface, alignment, assessment = _curved_fixture()
    result = place_profiles_from_alignment(
        alignment=alignment,
        design_surface=surface,
        assessment_polygon=assessment,
        role_mapping=ROLE_MAPPING,
        spacing_m=2.5,
    )

    assert result.supported
    normals = tuple(placement.downwall_xy for placement in result.placements)
    assert len(normals) >= 8
    assert result.diagnostics == ()
    assert max(normal[0] for normal in normals) - min(normal[0] for normal in normals) > 0.25
    assert all(
        first[0] * second[0] + first[1] * second[1] > 0.95
        for first, second in zip(normals, normals[1:])
    )
    assert not any(
        diagnostic.code == "profile_crossing_in_assessment"
        for diagnostic in result.diagnostics
    )


def test_face_not_alignment_order_chooses_physical_downwall_sign() -> None:
    common = dict(
        design_surface=_straight_surface(),
        assessment_polygon=_assessment(),
        role_mapping=ROLE_MAPPING,
        spacing_m=3.0,
    )

    forward = place_profiles_from_alignment(
        alignment=_straight_alignment(), **common
    )
    reverse = place_profiles_from_alignment(
        alignment=_straight_alignment(reverse=True), **common
    )

    assert _placement_signature(reverse) == _placement_signature(forward)
    assert all(item.downwall_xy == pytest.approx((0.0, 1.0)) for item in reverse.placements)


def test_multi_bench_design_remains_one_semantic_vertical_section() -> None:
    result = build_alignment_profile_sections(
        alignment=_straight_alignment(),
        design_surface=_straight_surface(),
        assessment_polygon=_assessment(),
        role_mapping=ROLE_MAPPING,
        spacing_m=3.0,
    )

    assert len(result.profiles) == 5
    assert all(
        profile.design_section.topology_signature == "FACE-BERM-FACE"
        for profile in result.profiles
    )
    assert all(profile.alignment.origin.z == pytest.approx(20.0) for profile in result.profiles)


def test_missing_face_support_omits_stations_with_deterministic_diagnostics() -> None:
    result = place_profiles_from_alignment(
        alignment=_straight_alignment(),
        design_surface=_straight_surface(),
        assessment_polygon=_polygon(
            (-1.0, -3.0), (13.0, -3.0), (13.0, -1.0), (-1.0, -1.0)
        ),
        role_mapping=ROLE_MAPPING,
        spacing_m=3.0,
    )

    assert not result.supported
    assert result.placements == ()
    assert tuple(item.code for item in result.diagnostics) == (
        "insufficient_face_support",
    ) * 5


def test_assessment_ring_rotation_and_orientation_do_not_rotate_profiles() -> None:
    first = _assessment()
    vertices = first.ring[:-1]
    rotated_reversed = tuple(reversed(vertices[2:] + vertices[:2]))
    second = PlanPolygon((*rotated_reversed, rotated_reversed[0]))
    common = dict(
        alignment=_straight_alignment(),
        design_surface=_straight_surface(),
        role_mapping=ROLE_MAPPING,
        spacing_m=3.0,
    )

    first_result = place_profiles_from_alignment(
        assessment_polygon=first, **common
    )
    second_result = place_profiles_from_alignment(
        assessment_polygon=second, **common
    )

    assert _placement_signature(second_result) == _placement_signature(first_result)


def test_actual_surface_is_intersected_only_after_identical_placement() -> None:
    common = dict(
        alignment=_straight_alignment(),
        design_surface=_straight_surface(),
        assessment_polygon=_assessment(),
        role_mapping=ROLE_MAPPING,
        spacing_m=3.0,
    )

    first = build_alignment_profile_sections(
        actual_surface=_straight_surface(actual_offset=0.5), **common
    )
    second = build_alignment_profile_sections(
        actual_surface=_straight_surface(actual_offset=-0.5), **common
    )

    assert _placement_signature(second.placement_result) == _placement_signature(
        first.placement_result
    )
    assert first.profiles[0].actual_segments != second.profiles[0].actual_segments
