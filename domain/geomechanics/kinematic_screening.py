"""Deterministic preliminary planar and wedge kinematic screening.

Angles follow the geological convention: dip direction/trend are clockwise
from north and plunge is positive downwards.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import atan2, cos, degrees, hypot, isfinite, radians, sin, sqrt, tan


@dataclass(frozen=True)
class Orientation:
    dip_deg: float
    dip_direction_deg: float
    name: str = ""


@dataclass(frozen=True)
class PlanarResult:
    joint: str
    dip_deg: float
    dip_direction_deg: float
    azimuth_difference_deg: float
    azimuth_pass: bool
    friction_pass: bool
    daylight_pass: bool

    @property
    def potential(self) -> bool:
        return self.azimuth_pass and self.friction_pass and self.daylight_pass


@dataclass(frozen=True)
class IntersectionLine:
    trend_deg: float
    plunge_deg: float
    vector: tuple[float, float, float]


@dataclass(frozen=True)
class WedgeResult:
    first: str
    second: str
    line: IntersectionLine | None
    criterion_values: tuple[float | None, float | None, float | None]
    criterion_passes: tuple[bool, bool, bool]
    friction_pass: bool

    @property
    def potential(self) -> bool:
        return all(self.criterion_passes) and self.friction_pass


def circular_azimuth_difference(first_deg: float, second_deg: float) -> float:
    """Return the shortest unsigned separation, including across north."""
    return abs((first_deg - second_deg + 180.0) % 360.0 - 180.0)


def q_prime(rqd: float | None, jn: float | None, jr: float | None, ja: float | None) -> float | None:
    values = (rqd, jn, jr, ja)
    if any(value is None or not isfinite(value) for value in values):
        return None
    if rqd < 0 or jn <= 0 or jr < 0 or ja <= 0:
        return None
    value = (rqd / jn) * (jr / ja)
    return value if isfinite(value) else None


def estimated_joint_friction_angle(jr: float | None, ja: float | None) -> float | None:
    if jr is None or ja is None or not isfinite(jr) or not isfinite(ja) or ja <= 0:
        return None
    ratio = jr / ja
    if ratio == -1:
        return None
    base = 52.0 * ratio / (1.0 + ratio) - 3.0
    if not isfinite(base) or base < 0:
        return None
    value = 8.33 * base ** 0.389
    return value if isfinite(value) else None


def indicative_cohesion_kpa(friction_angle_deg: float | None) -> float | None:
    if friction_angle_deg is None or not isfinite(friction_angle_deg):
        return None
    angle = friction_angle_deg
    value = 0.0051 * angle**3 - 0.1454 * angle**2 + 1.7557 * angle - 0.6301
    return value if isfinite(value) else None


def planar_screening(slope: Orientation, joints: list[Orientation], friction_angle_deg: float) -> list[PlanarResult]:
    results = []
    for index, joint in enumerate(joints, 1):
        difference = circular_azimuth_difference(slope.dip_direction_deg, joint.dip_direction_deg)
        results.append(PlanarResult(joint.name or f"J{index}", joint.dip_deg, joint.dip_direction_deg,
            difference, difference <= 20.0, friction_angle_deg < joint.dip_deg, joint.dip_deg < slope.dip_deg))
    return results


def plane_unit_normal(orientation: Orientation) -> tuple[float, float, float]:
    """Unit normal in east/north/up coordinates, consistently upward."""
    dip, azimuth = radians(orientation.dip_deg), radians(orientation.dip_direction_deg)
    return (-sin(dip) * sin(azimuth), -sin(dip) * cos(azimuth), cos(dip))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def intersection_line(first: Orientation, second: Orientation, tolerance: float = 1e-10) -> IntersectionLine | None:
    vector = _cross(plane_unit_normal(first), plane_unit_normal(second))
    length = sqrt(sum(value * value for value in vector))
    if not isfinite(length) or length <= tolerance:
        return None
    vector = tuple(value / length for value in vector)
    # Choose the geological down-plunge bearing. With Z positive up, this is
    # represented by the opposite (upward) directed line and a positive plunge.
    # This convention reproduces the supplied Wyllie/Mah project worksheet.
    if vector[2] < 0:
        vector = tuple(-value for value in vector)
    trend = degrees(atan2(vector[0], vector[1])) % 360.0
    plunge = degrees(atan2(vector[2], hypot(vector[0], vector[1])))
    return IntersectionLine(trend, plunge, vector)


def wedge_geometry(slope: Orientation, first: Orientation, second: Orientation) -> WedgeResult:
    """Apply the three comprehensive bench-wedge formation conditions.

    For the MVP bench, eta=+1 and the upper surface is horizontal.  The
    conditions respectively test outward intersection direction, daylight at
    the dipping face, and that the face ray is bounded by the two joint planes.
    Values are retained so the UI can expose an auditable diagnostic table.
    """
    names = sorted((first.name, second.name))
    line = intersection_line(first, second)
    if line is None:
        return WedgeResult(names[0], names[1], None, (None, None, None), (False, False, False), False)
    delta = radians(circular_azimuth_difference(line.trend_deg, slope.dip_direction_deg))
    criterion_1 = cos(delta)  # eta=+1: line points through the non-overhanging face
    criterion_2 = tan(radians(slope.dip_deg)) * criterion_1 - tan(radians(line.plunge_deg))
    # Face dip direction must fall between the two planes on the outward side.
    def signed(azimuth):
        return sin(radians((azimuth - slope.dip_direction_deg + 180) % 360 - 180))
    criterion_3 = -signed(first.dip_direction_deg) * signed(second.dip_direction_deg)
    passes = (criterion_1 >= 0.0, criterion_2 >= 0.0, criterion_3 >= 0.0)
    return WedgeResult(names[0], names[1], line, (criterion_1, criterion_2, criterion_3), passes, False)


def wedge_screening(slope: Orientation, joints: list[Orientation], friction_angle_deg: float) -> list[WedgeResult]:
    results = []
    for first, second in combinations(joints, 2):
        geometry = wedge_geometry(slope, first, second)
        friction = geometry.line is not None and geometry.line.plunge_deg > friction_angle_deg
        results.append(WedgeResult(geometry.first, geometry.second, geometry.line,
            geometry.criterion_values, geometry.criterion_passes, friction))
    return results
