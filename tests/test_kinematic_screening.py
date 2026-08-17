import math

import pytest

from domain.geomechanics.kinematic_screening import (
    Orientation, circular_azimuth_difference, estimated_joint_friction_angle,
    indicative_cohesion_kpa, intersection_line, planar_screening,
    plane_unit_normal, q_prime, wedge_geometry, wedge_screening,
)


def test_circular_azimuth_difference_and_planar_twenty_degree_boundary():
    assert circular_azimuth_difference(350, 10) == 20
    slope = Orientation(75, 350)
    results = planar_screening(slope, [Orientation(50, 10), Orientation(50, 10.001)], 30)
    assert results[0].azimuth_pass is True
    assert results[1].azimuth_pass is False


def test_q_prime_formula_and_unavailable_inputs():
    assert q_prime(72, 6, 3, 2) == 18
    for values in ((None, 6, 3, 2), (72, 0, 3, 2), (72, 6, 3, 0), (72, -1, 3, 2)):
        assert q_prime(*values) is None


def test_friction_angle_exact_formula_invalid_domain_and_cohesion():
    expected = 8.33 * (52 * (3 / 2) / (1 + 3 / 2) - 3) ** 0.389
    angle = estimated_joint_friction_angle(3, 2)
    assert angle == pytest.approx(expected)
    assert estimated_joint_friction_angle(0, 2) is None
    assert estimated_joint_friction_angle(3, 0) is None
    expected_cohesion = 0.0051 * angle**3 - 0.1454 * angle**2 + 1.7557 * angle - 0.6301
    assert indicative_cohesion_kpa(angle) == pytest.approx(expected_cohesion)


def test_planar_individual_failure_modes_and_pass():
    slope = Orientation(75, 120)
    results = planar_screening(slope, [Orientation(50, 150, "az"), Orientation(25, 120, "friction"),
        Orientation(80, 120, "daylight"), Orientation(50, 120, "pass")], 30)
    assert [result.potential for result in results] == [False, False, False, True]
    assert not results[0].azimuth_pass and not results[1].friction_pass and not results[2].daylight_pass


def test_plane_normal_is_unit_and_perpendicular_to_dip_strike():
    normal = plane_unit_normal(Orientation(60, 120))
    assert math.sqrt(sum(value**2 for value in normal)) == pytest.approx(1)
    assert normal[2] == pytest.approx(math.cos(math.radians(60)))


def test_intersection_regression_degenerate_and_pair_order_independence():
    first, second = Orientation(26, 83, "J1"), Orientation(76, 234, "J2")
    line = intersection_line(first, second); reverse = intersection_line(second, first)
    assert line.trend_deg == pytest.approx(147.0503, abs=1e-4)
    assert line.plunge_deg == pytest.approx(12.0475, abs=1e-4)
    assert reverse.trend_deg == pytest.approx(line.trend_deg)
    assert reverse.plunge_deg == pytest.approx(line.plunge_deg)
    assert intersection_line(first, Orientation(26, 83)) is None


def test_supplied_wedge_geometry_regression_and_friction_gate():
    slope = Orientation(75, 120, "Slope")
    first, second = Orientation(26, 83, "J1"), Orientation(76, 234, "J2")
    geometry = wedge_geometry(slope, first, second)
    assert geometry.criterion_passes == (True, True, True)
    assert wedge_geometry(slope, second, first).criterion_passes == geometry.criterion_passes
    assert wedge_screening(slope, [first, second], 10)[0].potential is True
    gated = wedge_screening(slope, [first, second], 15)[0]
    assert gated.criterion_passes == (True, True, True)
    assert gated.friction_pass is False and gated.potential is False
