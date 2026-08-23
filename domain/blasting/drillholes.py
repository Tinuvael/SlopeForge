from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, degrees, hypot, sqrt
from statistics import mean, median
from typing import Any, Iterable

from domain.geometry.types import DatamineLine


def _distance_3d(a: "DrillholePoint", b: "DrillholePoint") -> float:
    return sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2)


def _distance_xy(a: "DrillholePoint", b: "DrillholePoint") -> float:
    return hypot(b.x - a.x, b.y - a.y)


def _azimuth_deg(a: "DrillholePoint", b: "DrillholePoint") -> float | None:
    dx = b.x - a.x
    dy = b.y - a.y
    if hypot(dx, dy) <= 1e-12:
        return None
    return degrees(atan2(dx, dy)) % 360.0


def _inclination_deg(a: "DrillholePoint", b: "DrillholePoint") -> float | None:
    """Inclination from horizontal: 0° horizontal, 90° vertical."""
    horizontal = hypot(b.x - a.x, b.y - a.y)
    vertical = abs(b.z - a.z)
    if horizontal <= 1e-12 and vertical <= 1e-12:
        return None
    return degrees(atan2(vertical, horizontal))


def _wrapped_angle_difference(actual: float | None, design: float | None) -> float | None:
    if actual is None or design is None:
        return None
    return ((actual - design + 180.0) % 360.0) - 180.0


def _mean_azimuth(values: Iterable[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    from math import cos, radians, sin

    x = sum(sin(radians(value)) for value in usable)
    y = sum(cos(radians(value)) for value in usable)
    if abs(x) <= 1e-12 and abs(y) <= 1e-12:
        return None
    return degrees(atan2(x, y)) % 360.0


@dataclass(frozen=True)
class DrillholePoint:
    x: float
    y: float
    z: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "DrillholePoint":
        return cls(float(values["x"]), float(values["y"]), float(values["z"]))


@dataclass
class Drillhole:
    hole_id: str
    points: tuple[DrillholePoint, ...]
    engineering_group_id: str | None = None
    source_attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.hole_id = str(self.hole_id).strip()
        if not self.hole_id:
            raise ValueError("Drillhole ID is required")
        if len(self.points) < 2:
            raise ValueError("Drillhole geometry requires at least two points")
        if self.length_m <= 1e-9:
            raise ValueError("Drillhole geometry has zero length")

    @property
    def collar(self) -> DrillholePoint:
        return self.points[0]

    @property
    def toe(self) -> DrillholePoint:
        return self.points[-1]

    @property
    def length_m(self) -> float:
        return sum(_distance_3d(a, b) for a, b in zip(self.points, self.points[1:]))

    @property
    def azimuth_deg(self) -> float | None:
        return _azimuth_deg(self.collar, self.toe)

    @property
    def inclination_deg(self) -> float | None:
        return _inclination_deg(self.collar, self.toe)

    @property
    def has_stable_source_id(self) -> bool:
        """Whether the imported source ID is suitable as cross-revision identity.

        Direct/domain-created Drillhole objects keep the historical default of
        stable IDs. Import adapters can explicitly mark synthetic IDs (notably
        DXF entity handles/order) as unstable so they are never mistaken for a
        real blast-hole identifier.
        """
        return self.source_attributes.get("stable_hole_id") is not False

    def to_dict(self) -> dict[str, Any]:
        return {
            "hole_id": self.hole_id,
            "points": [point.to_dict() for point in self.points],
            "engineering_group_id": self.engineering_group_id,
            "source_attributes": dict(self.source_attributes),
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "Drillhole":
        return cls(
            hole_id=str(values["hole_id"]),
            points=tuple(DrillholePoint.from_dict(item) for item in values["points"]),
            engineering_group_id=values.get("engineering_group_id"),
            source_attributes=dict(values.get("source_attributes") or {}),
        )


@dataclass(frozen=True)
class DrillholeSummary:
    hole_count: int
    total_drilling_length_m: float
    mean_length_m: float
    median_length_m: float
    min_length_m: float
    max_length_m: float
    mean_azimuth_deg: float | None
    mean_inclination_deg: float | None
    min_collar_z: float
    max_collar_z: float
    min_toe_z: float
    max_toe_z: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class HoleMatch:
    design_hole_id: str | None
    actual_hole_id: str | None
    match_method: str
    collar_distance_xy_m: float | None = None
    collar_deviation_z_m: float | None = None
    collar_deviation_3d_m: float | None = None
    toe_distance_xy_m: float | None = None
    toe_deviation_z_m: float | None = None
    toe_deviation_3d_m: float | None = None
    design_length_m: float | None = None
    actual_length_m: float | None = None
    length_deviation_m: float | None = None
    length_deviation_percent: float | None = None
    design_azimuth_deg: float | None = None
    actual_azimuth_deg: float | None = None
    azimuth_deviation_deg: float | None = None
    design_inclination_deg: float | None = None
    actual_inclination_deg: float | None = None
    inclination_deviation_deg: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def drillhole_from_line(line: DatamineLine) -> Drillhole:
    if len(line.points) < 2:
        raise ValueError(f"Drillhole {line.source_id!r} has fewer than two points")
    points = tuple(DrillholePoint(float(p.x), float(p.y), float(p.z)) for p in line.points)
    # Blast-hole strings are not guaranteed to arrive directed. The higher end
    # is the collar for the supported open-pit drilling workflow; intermediate
    # survey stations remain in the original order relative to that direction.
    if points[-1].z > points[0].z:
        points = tuple(reversed(points))
    attrs = dict(line.source_attributes or {})
    attrs.setdefault("source_type", line.source_type)
    attrs.setdefault("assigned_type", line.assigned_type)
    attrs.setdefault("source_file", line.source_file)
    attrs.setdefault("import_order", line.import_order)
    return Drillhole(str(line.source_id), points, source_attributes=attrs)


def drillholes_from_lines(lines: Iterable[DatamineLine]) -> tuple[Drillhole, ...]:
    holes: list[Drillhole] = []
    ids: set[str] = set()
    for line in lines:
        try:
            hole = drillhole_from_line(line)
        except ValueError:
            continue
        if hole.hole_id in ids:
            raise ValueError(f"Duplicate drillhole ID: {hole.hole_id}")
        ids.add(hole.hole_id)
        holes.append(hole)
    if not holes:
        raise ValueError("Geometry file contains no usable drillholes")
    return tuple(holes)


def summarize_drillholes(holes: Iterable[Drillhole]) -> DrillholeSummary:
    values = tuple(holes)
    if not values:
        raise ValueError("Drillhole summary requires at least one hole")
    lengths = [hole.length_m for hole in values]
    inclinations = [hole.inclination_deg for hole in values if hole.inclination_deg is not None]
    return DrillholeSummary(
        hole_count=len(values),
        total_drilling_length_m=sum(lengths),
        mean_length_m=mean(lengths),
        median_length_m=median(lengths),
        min_length_m=min(lengths),
        max_length_m=max(lengths),
        mean_azimuth_deg=_mean_azimuth(hole.azimuth_deg for hole in values),
        mean_inclination_deg=mean(inclinations) if inclinations else None,
        min_collar_z=min(hole.collar.z for hole in values),
        max_collar_z=max(hole.collar.z for hole in values),
        min_toe_z=min(hole.toe.z for hole in values),
        max_toe_z=max(hole.toe.z for hole in values),
    )


def _match_pair(design: Drillhole, actual: Drillhole, method: str) -> HoleMatch:
    collar_xy = _distance_xy(design.collar, actual.collar)
    collar_z = actual.collar.z - design.collar.z
    toe_xy = _distance_xy(design.toe, actual.toe)
    toe_z = actual.toe.z - design.toe.z
    length_delta = actual.length_m - design.length_m
    length_percent = (
        length_delta / design.length_m * 100.0
        if design.length_m > 1e-12
        else None
    )
    return HoleMatch(
        design_hole_id=design.hole_id,
        actual_hole_id=actual.hole_id,
        match_method=method,
        collar_distance_xy_m=collar_xy,
        collar_deviation_z_m=collar_z,
        collar_deviation_3d_m=sqrt(collar_xy ** 2 + collar_z ** 2),
        toe_distance_xy_m=toe_xy,
        toe_deviation_z_m=toe_z,
        toe_deviation_3d_m=sqrt(toe_xy ** 2 + toe_z ** 2),
        design_length_m=design.length_m,
        actual_length_m=actual.length_m,
        length_deviation_m=length_delta,
        length_deviation_percent=length_percent,
        design_azimuth_deg=design.azimuth_deg,
        actual_azimuth_deg=actual.azimuth_deg,
        azimuth_deviation_deg=_wrapped_angle_difference(actual.azimuth_deg, design.azimuth_deg),
        design_inclination_deg=design.inclination_deg,
        actual_inclination_deg=actual.inclination_deg,
        inclination_deviation_deg=(
            None
            if actual.inclination_deg is None or design.inclination_deg is None
            else actual.inclination_deg - design.inclination_deg
        ),
    )


def _stable_id_is_compatible(
    design: Drillhole,
    actual: Drillhole,
    all_design: tuple[Drillhole, ...],
) -> bool:
    """Reject only stable IDs that strongly contradict collar geometry."""
    if not design.has_stable_source_id or not actual.has_stable_source_id:
        return False
    same_distance = _distance_xy(design.collar, actual.collar)
    alternatives = [
        _distance_xy(candidate.collar, actual.collar)
        for candidate in all_design
        if candidate.hole_id != design.hole_id
    ]
    if not alternatives:
        return True
    nearest_alternative = min(alternatives)
    if nearest_alternative <= 1e-9:
        return same_distance <= 1e-9
    return same_distance <= nearest_alternative * 3.0


def _geometry_match_method(
    chosen_distance: float,
    actual: Drillhole,
    design_candidates: tuple[Drillhole, ...],
) -> str:
    """Classify deterministic collar matching without inventing site tolerances.

    Confidence is relative to competing design collars rather than an absolute
    engineering tolerance. A pair is high-confidence when the chosen collar is
    the actual hole's nearest candidate and the second candidate is at least
    twice as far away. With one remaining candidate the assignment is unique.
    Dense/equidistant layouts are retained but explicitly flagged for review.
    """
    distances = sorted(_distance_xy(candidate.collar, actual.collar) for candidate in design_candidates)
    if not distances:
        return "matched_geometry_low_confidence"
    nearest = distances[0]
    if chosen_distance > nearest + 1e-9:
        return "matched_geometry_low_confidence"
    if len(distances) == 1:
        return "matched_geometry_high_confidence"
    second = distances[1]
    if nearest <= 1e-9:
        return (
            "matched_geometry_high_confidence"
            if second > 1e-9
            else "matched_geometry_low_confidence"
        )
    return (
        "matched_geometry_high_confidence"
        if second / nearest >= 2.0
        else "matched_geometry_low_confidence"
    )


def match_actual_to_design(
    design_holes: Iterable[Drillhole],
    actual_holes: Iterable[Drillhole],
) -> tuple[HoleMatch, ...]:
    """Deterministic one-to-one matching with explicit ambiguity state.

    Only explicitly stable source IDs are authoritative. Remaining holes are
    proposed by nearest collar under one-to-one constraints. Dense or contested
    geometric proposals are kept as low-confidence rather than being silently
    presented as definitive matches.
    """
    design = tuple(design_holes)
    actual = tuple(actual_holes)
    design_by_id = {hole.hole_id: hole for hole in design}
    actual_by_id = {hole.hole_id: hole for hole in actual}

    matched_design: set[str] = set()
    matched_actual: set[str] = set()
    matches: list[HoleMatch] = []

    for hole_id in sorted(set(design_by_id) & set(actual_by_id)):
        design_hole = design_by_id[hole_id]
        actual_hole = actual_by_id[hole_id]
        if not _stable_id_is_compatible(design_hole, actual_hole, design):
            continue
        matches.append(_match_pair(design_hole, actual_hole, "matched_by_id"))
        matched_design.add(hole_id)
        matched_actual.add(hole_id)

    remaining_design = tuple(hole for hole in design if hole.hole_id not in matched_design)
    remaining_actual = tuple(hole for hole in actual if hole.hole_id not in matched_actual)
    candidates = sorted(
        (
            _distance_xy(design_hole.collar, actual_hole.collar),
            design_hole.hole_id,
            actual_hole.hole_id,
            design_hole,
            actual_hole,
        )
        for design_hole in remaining_design
        for actual_hole in remaining_actual
    )
    for distance, _design_id, _actual_id, design_hole, actual_hole in candidates:
        if design_hole.hole_id in matched_design or actual_hole.hole_id in matched_actual:
            continue
        method = _geometry_match_method(distance, actual_hole, remaining_design)
        matches.append(_match_pair(design_hole, actual_hole, method))
        matched_design.add(design_hole.hole_id)
        matched_actual.add(actual_hole.hole_id)

    for hole in design:
        if hole.hole_id not in matched_design:
            matches.append(HoleMatch(hole.hole_id, None, "unmatched_design"))
    for hole in actual:
        if hole.hole_id not in matched_actual:
            matches.append(HoleMatch(None, hole.hole_id, "unmatched_actual"))

    return tuple(matches)
