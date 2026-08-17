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


def _worksheet_unit_normal(orientation: Orientation) -> tuple[float, float, float]:
    """Normal convention used by the supplied Maple/Wyllie-Mah worksheet.

    The worksheet defines Nx=sin(dip)sin(azimuth), Ny=sin(dip)cos(azimuth),
    Nz=cos(dip).  Keep this convention local to the wedge-formation criteria so
    their signed numeric regression remains directly auditable against the
    supplied calculation.
    """
    dip, azimuth = radians(orientation.dip_deg), radians(orientation.dip_direction_deg)
    return (sin(dip) * sin(azimuth), sin(dip) * cos(azimuth), cos(dip))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _dot(a, b):
    return sum(first * second for first, second in zip(a, b))


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


def wedge_geometry(slope: Orientation, first: Orientation, second: Orientation,
                   tolerance: float = 1e-10) -> WedgeResult:
    """Apply the three supplied Maple/Wyllie-Mah bench-wedge criteria exactly.

    The source worksheet uses a non-overhanging face (eta=+1), a horizontal
    upper surface (dipU=0), and upper-surface azimuth aligned with the face.
    Its three signed criteria are retained verbatim in vector form and a wedge
    is geometrically formed only when every value is strictly negative.
    """
    names = sorted((first.name, second.name))
    line = intersection_line(first, second, tolerance)
    if line is None:
        return WedgeResult(names[0], names[1], None, (None, None, None), (False, False, False), False)

    # Worksheet notation: B=bench face, U=upper surface, 1/2=joint planes.
    normal_b = _worksheet_unit_normal(slope)
    upper = Orientation(0.0, slope.dip_direction_deg, "Upper")
    normal_u = _worksheet_unit_normal(upper)
    normal_1 = _worksheet_unit_normal(first)
    normal_2 = _worksheet_unit_normal(second)

    # iix/iiy/iiz in the worksheet are the unnormalised N2 x N1 vector.
    intersection_raw = _cross(normal_2, normal_1)
    iiz = intersection_raw[2]
    if not isfinite(iiz) or abs(iiz) <= tolerance:
        return WedgeResult(names[0], names[1], line, (None, None, None), (False, False, False), False)

    # gg = NB x N1; p = i . NU; q = gg . N2.
    gg = _cross(normal_b, normal_1)
    p = _dot(intersection_raw, normal_u)
    q = _dot(gg, normal_2)

    eta = 1.0
    slope_dip = radians(slope.dip_deg)
    upper_dip = radians(upper.dip_deg)

    # Exact signed criteria from the supplied worksheet (page 4).
    criterion_1 = -iiz * p
    criterion_2 = eta * q / (-iiz)
    criterion_3 = (
        eta * (cos(slope_dip) - q / (-iiz)) * tan(upper_dip)
        - sqrt(max(0.0, 1.0 - cos(slope_dip) ** 2))
    )
    values = (criterion_1, criterion_2, criterion_3)
    if not all(isfinite(value) for value in values):
        return WedgeResult(names[0], names[1], line, values, (False, False, False), False)
    passes = tuple(value < 0.0 for value in values)
    return WedgeResult(names[0], names[1], line, values, passes, False)


def wedge_screening(slope: Orientation, joints: list[Orientation], friction_angle_deg: float) -> list[WedgeResult]:
    results = []
    for first, second in combinations(joints, 2):
        geometry = wedge_geometry(slope, first, second)
        friction = geometry.line is not None and geometry.line.plunge_deg > friction_angle_deg
        results.append(WedgeResult(geometry.first, geometry.second, geometry.line,
            geometry.criterion_values, geometry.criterion_passes, friction))
    return results
