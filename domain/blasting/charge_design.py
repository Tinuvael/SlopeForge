"""Pure types for composable downhole charge designs.

Depth is measured from the collar (0 m) and increases downhole.  Air is the
absence of a component and is therefore never stored as a component.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from enum import Enum
import math
import re
from typing import Iterable


class ChargeDesignValidationError(ValueError):
    """A product or charge design violates an engineering invariant."""


class ExplosiveProductKind(str, Enum):
    BULK = "bulk"
    CARTRIDGE = "cartridge"


class ChargeComponentKind(str, Enum):
    BULK_EXPLOSIVE = "bulk_explosive"
    CARTRIDGE_EXPLOSIVE = "cartridge_explosive"
    STEMMING = "stemming"


def _positive(value: float | None, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if value is None or not math.isfinite(value) or value <= 0:
        raise ChargeDesignValidationError(f"{label} must be a finite value greater than zero")


@dataclass(frozen=True)
class ExplosiveProductSnapshot:
    source_product_id: int
    name: str
    kind: ExplosiveProductKind
    display_color: str
    density_kg_m3: float | None = None
    cartridge_diameter_mm: float | None = None
    cartridge_mass_kg: float | None = None
    default_pitch_m: float | None = None


@dataclass
class ExplosiveProduct:
    id: int
    name: str
    kind: ExplosiveProductKind
    display_color: str
    enabled: bool = True
    density_kg_m3: float | None = None
    cartridge_diameter_mm: float | None = None
    cartridge_mass_kg: float | None = None
    default_pitch_m: float | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ChargeDesignValidationError("Product name is required")
        try:
            self.kind = ExplosiveProductKind(self.kind)
        except ValueError as exc:
            raise ChargeDesignValidationError("Product kind must be bulk or cartridge") from exc
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.display_color):
            raise ChargeDesignValidationError("Display color must use #RRGGBB")
        self.display_color = self.display_color.upper()
        if self.kind is ExplosiveProductKind.BULK:
            _positive(self.density_kg_m3, "Density")
            if any(value is not None for value in (
                    self.cartridge_diameter_mm, self.cartridge_mass_kg, self.default_pitch_m)):
                raise ChargeDesignValidationError("Bulk products cannot have cartridge properties")
        else:
            _positive(self.cartridge_diameter_mm, "Cartridge diameter")
            _positive(self.cartridge_mass_kg, "Cartridge mass")
            _positive(self.default_pitch_m, "Default pitch", optional=True)
            if self.density_kg_m3 is not None:
                raise ChargeDesignValidationError("Cartridge products cannot have bulk density")

    def snapshot(self) -> ExplosiveProductSnapshot:
        return ExplosiveProductSnapshot(
            source_product_id=self.id, name=self.name, kind=self.kind,
            display_color=self.display_color, density_kg_m3=self.density_kg_m3,
            cartridge_diameter_mm=self.cartridge_diameter_mm,
            cartridge_mass_kg=self.cartridge_mass_kg,
            default_pitch_m=self.default_pitch_m,
        )


@dataclass(frozen=True)
class ChargeComponent:
    id: str
    kind: ChargeComponentKind
    start_depth_m: float
    end_depth_m: float
    product_snapshot: ExplosiveProductSnapshot | None = None
    cartridge_pitch_m: float | None = None

    def __post_init__(self) -> None:
        try:
            kind = ChargeComponentKind(self.kind)
        except ValueError as exc:
            raise ChargeDesignValidationError("Unknown charge component kind") from exc
        object.__setattr__(self, "kind", kind)
        if (not math.isfinite(self.start_depth_m) or not math.isfinite(self.end_depth_m)
                or self.start_depth_m < 0 or self.end_depth_m <= self.start_depth_m):
            raise ChargeDesignValidationError("Component depths must be finite and start before end")
        if kind is ChargeComponentKind.STEMMING:
            if self.product_snapshot is not None or self.cartridge_pitch_m is not None:
                raise ChargeDesignValidationError("Stemming cannot have a product or cartridge pitch")
        elif kind is ChargeComponentKind.BULK_EXPLOSIVE:
            if self.product_snapshot is None or self.product_snapshot.kind is not ExplosiveProductKind.BULK:
                raise ChargeDesignValidationError("Bulk component requires a bulk product snapshot")
            if self.cartridge_pitch_m is not None:
                raise ChargeDesignValidationError("Bulk component cannot have cartridge pitch")
        else:
            if self.product_snapshot is None or self.product_snapshot.kind is not ExplosiveProductKind.CARTRIDGE:
                raise ChargeDesignValidationError("Cartridge component requires a cartridge product snapshot")
            _positive(self.cartridge_pitch_m, "Cartridge pitch")

    @property
    def length_m(self) -> float:
        return self.end_depth_m - self.start_depth_m


def validate_components(components: Iterable[ChargeComponent], hole_depth_m: float) -> None:
    _positive(hole_depth_m, "Hole depth")
    ordered = sorted(components, key=lambda item: (item.start_depth_m, item.end_depth_m))
    for component in ordered:
        if component.end_depth_m > hole_depth_m:
            raise ChargeDesignValidationError("Component extends beyond the hole depth")
    for previous, current in zip(ordered, ordered[1:]):
        if current.start_depth_m < previous.end_depth_m:
            raise ChargeDesignValidationError("Charge components must not overlap")


def available_air_intervals(
        hole_depth_m: float, components: Iterable[ChargeComponent]) -> list[tuple[float, float]]:
    items = list(components)
    validate_components(items, hole_depth_m)
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for component in sorted(items, key=lambda item: (item.start_depth_m, item.end_depth_m)):
        if cursor < component.start_depth_m:
            gaps.append((cursor, component.start_depth_m))
        cursor = component.end_depth_m
    if cursor < hole_depth_m:
        gaps.append((cursor, hole_depth_m))
    return gaps


def cartridge_depths(component: ChargeComponent) -> tuple[float, ...]:
    """Return cartridge centres using the inclusive start-plus-pitch convention.

    Decimal arithmetic derives every position from the deck start (rather than
    repeatedly adding a binary float), so the end-point decision is stable.
    """
    if component.kind is not ChargeComponentKind.CARTRIDGE_EXPLOSIVE:
        raise ChargeDesignValidationError("Cartridge depths require a cartridge component")
    pitch = component.cartridge_pitch_m
    if pitch is None or not math.isfinite(pitch) or pitch <= 0:
        raise ChargeDesignValidationError("Cartridge pitch must be a finite value greater than zero")
    start = Decimal(str(component.start_depth_m))
    end = Decimal(str(component.end_depth_m))
    step = Decimal(str(pitch))
    count = int(((end - start) / step).to_integral_value(rounding=ROUND_FLOOR)) + 1
    return tuple(float(start + step * index) for index in range(count))
