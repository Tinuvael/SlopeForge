from math import sqrt

import pytest

from domain.blasting.drillholes import (
    Drillhole,
    DrillholePoint,
    drillhole_from_line,
    match_actual_to_design,
    summarize_drillholes,
)
from domain.geometry.types import DatamineLine, DataminePoint


def _point(x, y, z, row):
    return DataminePoint(x, y, z, row)


def _line(source_id, coords):
    return DatamineLine(
        source_id,
        [_point(x, y, z, index + 1) for index, (x, y, z) in enumerate(coords)],
    )


def _hole(hole_id, collar, toe):
    return Drillhole(
        hole_id,
        (DrillholePoint(*collar), DrillholePoint(*toe)),
    )


def test_imported_line_is_normalized_collar_to_toe_without_losing_intermediate_points():
    line = _line("H-1", [(2, 2, 590), (1, 1, 610), (0, 0, 630)])

    hole = drillhole_from_line(line)

    assert hole.collar == DrillholePoint(0, 0, 630)
    assert hole.toe == DrillholePoint(2, 2, 590)
    assert hole.points[1] == DrillholePoint(1, 1, 610)


def test_drillhole_metrics_use_full_polyline_length_and_endpoint_orientation():
    hole = Drillhole(
        "H-1",
        (
            DrillholePoint(0, 0, 630),
            DrillholePoint(3, 0, 626),
            DrillholePoint(6, 0, 622),
        ),
    )

    assert hole.length_m == pytest.approx(10.0)
    assert hole.azimuth_deg == pytest.approx(90.0)
    assert hole.inclination_deg == pytest.approx(53.130102, rel=1e-6)


def test_dataset_summary_derives_counts_lengths_orientation_and_elevation_ranges():
    holes = (
        _hole("A", (0, 0, 630), (0, 0, 620)),
        _hole("B", (10, 0, 632), (10, 10, 622)),
    )

    summary = summarize_drillholes(holes)

    assert summary.hole_count == 2
    assert summary.total_drilling_length_m == pytest.approx(10 + sqrt(200))
    assert summary.min_length_m == pytest.approx(10)
    assert summary.max_length_m == pytest.approx(sqrt(200))
    assert summary.min_collar_z == 630
    assert summary.max_collar_z == 632
    assert summary.min_toe_z == 620
    assert summary.max_toe_z == 622
    assert summary.mean_inclination_deg is not None


def test_matching_prefers_compatible_stable_id_before_geometric_proposals():
    design = (
        _hole("H-1", (0, 0, 630), (0, 0, 620)),
        _hole("H-2", (10, 0, 630), (10, 0, 620)),
    )
    actual = (
        _hole("H-1", (0.2, 0, 630), (0.2, 0, 620)),
        _hole("ACTUAL-2", (10.1, 0, 630), (10.1, 0, 620)),
    )

    matches = match_actual_to_design(design, actual)
    by_actual = {item.actual_hole_id: item for item in matches if item.actual_hole_id}

    assert by_actual["H-1"].design_hole_id == "H-1"
    assert by_actual["H-1"].match_method == "matched_by_id"
    assert by_actual["ACTUAL-2"].design_hole_id == "H-2"
    assert by_actual["ACTUAL-2"].match_method == "matched_geometry_high_confidence"


def test_geometric_matching_is_one_to_one_and_reports_missing_or_additional_holes():
    design = (
        _hole("D-1", (0, 0, 630), (0, 0, 620)),
        _hole("D-2", (10, 0, 630), (10, 0, 620)),
        _hole("D-3", (20, 0, 630), (20, 0, 620)),
    )
    actual = (
        _hole("A-1", (0.2, 0, 629.5), (0.5, 0, 618)),
        _hole("A-2", (10.1, 0, 630), (11, 0, 619)),
        _hole("A-EXTRA", (100, 100, 630), (100, 100, 620)),
        _hole("A-EXTRA-2", (200, 200, 630), (200, 200, 620)),
    )

    matches = match_actual_to_design(design, actual)

    matched = [item for item in matches if item.design_hole_id and item.actual_hole_id]
    assert len(matched) == 3
    assert len({item.design_hole_id for item in matched}) == 3
    assert len({item.actual_hole_id for item in matched}) == 3
    assert sum(item.match_method == "unmatched_actual" for item in matches) == 1
    assert sum(item.match_method == "unmatched_design" for item in matches) == 0


def test_matched_pair_exposes_complete_collar_toe_length_and_orientation_qa():
    design = (_hole("D", (0, 0, 630), (0, 0, 620)),)
    actual = (_hole("A", (3, 4, 632), (6, 8, 618)),)

    match = match_actual_to_design(design, actual)[0]

    assert match.collar_distance_xy_m == pytest.approx(5)
    assert match.collar_deviation_z_m == pytest.approx(2)
    assert match.collar_deviation_3d_m == pytest.approx(sqrt(29))
    assert match.toe_distance_xy_m == pytest.approx(10)
    assert match.toe_deviation_z_m == pytest.approx(-2)
    assert match.toe_deviation_3d_m == pytest.approx(sqrt(104))
    assert match.design_length_m == pytest.approx(10)
    assert match.actual_length_m is not None
    assert match.length_deviation_m is not None
    assert match.length_deviation_percent is not None
    assert match.design_azimuth_deg is None
    assert match.actual_azimuth_deg is not None
    assert match.design_inclination_deg == pytest.approx(90)
    assert match.actual_inclination_deg is not None
    assert match.inclination_deviation_deg is not None
