from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot
from statistics import mean, median
from typing import Iterable

from domain.blasting.drillholes import Drillhole


def _xy_distance(a: Drillhole, b: Drillhole) -> float:
    return hypot(b.collar.x - a.collar.x, b.collar.y - a.collar.y)


def order_contour_holes(holes: Iterable[Drillhole]) -> tuple[Drillhole, ...]:
    """Deterministically order a single contour collar chain by local proximity.

    The farthest collar pair supplies stable end candidates, then a nearest-unused
    walk follows the contour. This works for straight and ordinary curved contour
    rows without pretending that a production-grid nearest-neighbour average is
    a contour spacing model.
    """
    values = tuple(holes)
    if len(values) <= 1:
        return values
    farthest = max(
        (
            (_xy_distance(a, b), a.hole_id, b.hole_id, a, b)
            for index, a in enumerate(values)
            for b in values[index + 1 :]
        ),
        key=lambda item: (item[0], item[1], item[2]),
    )
    start = min((farthest[3], farthest[4]), key=lambda hole: hole.hole_id)
    remaining = {hole.hole_id: hole for hole in values}
    remaining.pop(start.hole_id)
    ordered = [start]
    while remaining:
        current = ordered[-1]
        next_hole = min(
            remaining.values(),
            key=lambda candidate: (_xy_distance(current, candidate), candidate.hole_id),
        )
        ordered.append(next_hole)
        remaining.pop(next_hole.hole_id)
    return tuple(ordered)


@dataclass(frozen=True)
class ContourDrillingSummary:
    ordered_hole_ids: tuple[str, ...]
    line_length_m: float
    mean_spacing_m: float | None
    median_spacing_m: float | None
    min_spacing_m: float | None
    max_spacing_m: float | None
    alignment_azimuth_deg: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "ordered_hole_ids": list(self.ordered_hole_ids),
            "line_length_m": self.line_length_m,
            "mean_spacing_m": self.mean_spacing_m,
            "median_spacing_m": self.median_spacing_m,
            "min_spacing_m": self.min_spacing_m,
            "max_spacing_m": self.max_spacing_m,
            "alignment_azimuth_deg": self.alignment_azimuth_deg,
        }


def summarize_contour_drilling(holes: Iterable[Drillhole]) -> ContourDrillingSummary:
    ordered = order_contour_holes(holes)
    if not ordered:
        raise ValueError("Contour drilling summary requires at least one hole")
    spacings = [_xy_distance(a, b) for a, b in zip(ordered, ordered[1:])]
    first = ordered[0].collar
    last = ordered[-1].collar
    dx = last.x - first.x
    dy = last.y - first.y
    alignment = None if hypot(dx, dy) <= 1e-12 else degrees(atan2(dx, dy)) % 360.0
    return ContourDrillingSummary(
        ordered_hole_ids=tuple(hole.hole_id for hole in ordered),
        line_length_m=sum(spacings),
        mean_spacing_m=mean(spacings) if spacings else None,
        median_spacing_m=median(spacings) if spacings else None,
        min_spacing_m=min(spacings) if spacings else None,
        max_spacing_m=max(spacings) if spacings else None,
        alignment_azimuth_deg=alignment,
    )
