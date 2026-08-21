"""Versioned engineering cards attached to stable BlastEvent identifiers."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields
from datetime import datetime
from math import isfinite
from typing import Any
from uuid import uuid4

from domain.blasting.entities import BlastEvent, utc_now
from domain.geometry.types import PlanPolygon
from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ExplosiveClass, ExplosiveProductKind, ExplosiveProductSnapshot,
    component_explosive_mass_kg,
)

PRODUCTION_GROUP_TYPES = {
    "main_pattern": "Основная сеть", "inner_buffer": "Внутренний буферный ряд",
    "outer_buffer": "Внешний буферный ряд", "buffer": "Буферные скважины",
    "cut_opening": "Врубовые / разрезные", "crest": "Бровочные",
    "toe": "Подошвенные", "relief": "Разгрузочные",
    "auxiliary": "Вспомогательные", "other": "Другой тип",
}
CONTOUR_GROUP_TYPES = {
    "contour_line": "Контурный ряд", "presplit_line": "Presplit",
    "midsplit_line": "Midsplit", "postsplit_line": "Postsplit",
    "line_drilling": "Line drilling", "inner_buffer": "Внутренний буфер",
    "outer_buffer": "Внешний буфер", "trim_row": "Trim", "other": "Другой тип",
}
CONTROLLED_BLASTING_METHODS = {
    "buffer_cushion": "Буферное / cushion blasting", "trim": "Оконтуривающее / trim blasting",
    "presplit": "Предварительное щелеобразование / presplit",
    "midsplit": "Промежуточное щелеобразование / midsplit",
    "postsplit": "Последующее щелеобразование / postsplit",
    "line_drilling": "Бурение по линии незаряженных скважин", "other": "Другой метод",
}

# Canonical Barton Q-system ratings exposed by the active Geomechanics UI.
# Keep these values centralized so UI choices and persisted-domain validation cannot drift.
BARTON_JN_VALUES = (0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 9.0, 12.0, 15.0, 20.0)
BARTON_JR_VALUES = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0)
BARTON_JA_VALUES = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 9.0, 10.0, 12.0, 13.0, 20.0)
BARTON_JW_VALUES = (1.0, 0.66, 0.5, 0.33, 0.2, 0.1)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def polygon_area_m2(polygon: PlanPolygon | None) -> float | None:
    """Shoelace area in domain X/Y coordinates (never scene coordinates)."""
    if polygon is None:
        return None
    return abs(sum(a.x * b.y - b.x * a.y for a, b in zip(polygon.ring, polygon.ring[1:]))) / 2


def nominal_contour_line_length(group: "BlastDrillingGroup | None") -> float | None:
    """MVP product length for the primary contour row: holes × spacing."""
    if group is None or group.hole_count is None or group.spacing_m is None:
        return None
    return group.hole_count * group.spacing_m


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / denominator
    return value if isfinite(value) else None


def _is_allowed_rating(value: float, allowed: tuple[float, ...]) -> bool:
    return any(abs(value - candidate) <= 1e-9 for candidate in allowed)


@dataclass
class ManualValue:
    calculated_value: float | None = None
    manual_value: float | None = None

    @property
    def accepted_value(self) -> float | None:
        return self.manual_value if self.manual_value is not None else self.calculated_value


@dataclass
class CommonParameters:
    project_date: str | None = None; blast_date: str | None = None; block_name: str = ""
    mine_area: str = ""; wall_sector: str = ""; bench: str = ""; working_horizon: float | None = None
    block_type: str = ""; source_geometry_revision_id: str = ""; source_csv: str = ""; comments: str = ""


@dataclass
class DesignSlopeOrientation:
    azimuth_deg: float | None = None
    angle_deg: float | None = None

    def __post_init__(self):
        if self.azimuth_deg is not None and (not isfinite(self.azimuth_deg) or not 0 <= self.azimuth_deg < 360):
            raise ValueError("Design slope azimuth must be at least 0 and less than 360 degrees")
        if self.angle_deg is not None and (not isfinite(self.angle_deg) or not 0 <= self.angle_deg <= 90):
            raise ValueError("Design slope angle must be between 0 and 90 degrees")


@dataclass
class JointSetOrientation:
    dip_deg: float
    dip_direction_deg: float
    spacing_m: float | None = None
    persistence_m: float | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.dip_deg) or not 0 <= self.dip_deg <= 90:
            raise ValueError("Joint-set dip must be between 0 and 90 degrees")
        if not isfinite(self.dip_direction_deg) or not 0 <= self.dip_direction_deg < 360:
            raise ValueError("Joint-set dip direction must be at least 0 and less than 360 degrees")
        for name in ("spacing_m", "persistence_m"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError(f"Joint-set {name} must be finite and positive")


@dataclass
class GeomechanicalParameters:
    lithology: str = ""
    rock_density_t_m3: float | None = None
    ucs_mpa: float | None = None
    # Compatibility-only reader for pre-#102 payloads; never emitted or edited.
    q_value: float | None = field(default=None, repr=False)
    rqd_percent: float | None = None
    gsi: float | None = None
    ff: float | None = None
    joint_sets: list[JointSetOrientation] = field(default_factory=list)
    jw: float | None = None
    jn: float | None = None
    jr: float | None = None
    ja: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if len(self.joint_sets) > 5:
            raise ValueError("Geomechanics may contain at most five joint sets")
        for name in ("rock_density_t_m3", "ucs_mpa", "q_value", "rqd_percent", "gsi", "ff", "jw", "jn", "jr", "ja"):
            value = getattr(self, name)
            if value is not None and not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.ucs_mpa is not None and self.ucs_mpa < 0:
            raise ValueError("UCS must be non-negative")
        if self.rock_density_t_m3 is not None and self.rock_density_t_m3 <= 0:
            raise ValueError("Rock density must be positive")
        if self.rqd_percent is not None and not 0 <= self.rqd_percent <= 100:
            raise ValueError("RQD must be between 0 and 100 percent")
        if self.gsi is not None and not 1 <= self.gsi <= 100:
            raise ValueError("GSI must be between 1 and 100")
        if self.ff is not None and self.ff < 0:
            raise ValueError("FF must be non-negative")
        for name, allowed in (
            ("Jn", BARTON_JN_VALUES), ("Jr", BARTON_JR_VALUES),
            ("Ja", BARTON_JA_VALUES), ("Jw", BARTON_JW_VALUES),
        ):
            value = getattr(self, name.lower())
            if value is not None and not _is_allowed_rating(value, allowed):
                choices = ", ".join(f"{item:g}" for item in allowed)
                raise ValueError(f"{name} must be one of: {choices}")

    def minimum_complete(self) -> bool:
        return self.ucs_mpa is not None and any(
            value is not None for value in (self.rqd_percent, self.gsi, self.ff, self.jn, self.jr, self.ja)
        )


@dataclass
class BlastDrillingGroup:
    id: str = field(default_factory=lambda: _new_id("DG")); group_type: str = "main_pattern"
    custom_type_name: str = ""; name: str = "Основная сеть"; sequence_order: int = 1; included: bool = True
    hole_count: int | None = None; diameter_mm: float | None = None; average_depth_m: float | None = None
    subdrill_m: float | None = None; burden_m: float | None = None; spacing_m: float | None = None
    row_count: int | None = None; inclination_deg: float | None = None; azimuth_deg: float | None = None
    line_offset_m: float | None = None; toe_standoff_m: float | None = None; stemming_length_m: float | None = None
    charge_mass_per_hole_kg: float | None = None; charge_concentration_kg_per_m: float | None = None
    total_charge_mass_kg: float | None = None; explosive_type: str = ""; charge_construction_text: str = ""
    initiation_sequence: str = ""; delay_ms: float | None = None; planned_drilling_length_m: float | None = None
    air_deck_count: int | None = None; deck_notes: str = ""; charge_decks: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    charge_components: list[ChargeComponent] = field(default_factory=list)
    # Read-only migration buffer.  It is deliberately omitted from new JSON.
    legacy_actual_drilling_length_m: float | None = field(default=None, repr=False)

    def drilling_length(self) -> float | None:
        if not self.included: return 0.0
        if self.hole_count is None or self.average_depth_m is None: return None
        return self.hole_count * self.average_depth_m

    def explosive_mass_per_hole_kg(self) -> float | None:
        if not self.charge_components: return 0.0
        try: return sum(component_explosive_mass_kg(item, self.diameter_mm) for item in self.charge_components)
        except ValueError: return None

    def total_explosive_mass(self) -> float | None:
        per_hole = self.explosive_mass_per_hole_kg()
        return None if per_hole is None or self.hole_count is None else per_hole * self.hole_count

    def stemming_total_m(self) -> float:
        return sum(item.length_m for item in self.charge_components if item.kind is ChargeComponentKind.STEMMING)

    def explosive_names(self) -> str:
        return ", ".join(dict.fromkeys(item.product_snapshot.name for item in self.charge_components if item.product_snapshot))


@dataclass
class ProductionParameters:
    drilling_area_m2: ManualValue = field(default_factory=ManualValue)
    average_hole_depth_m: float | None = None; subdrill_m: float | None = None
    average_depth_without_subdrill_m: float | None = None
    block_volume_m3: ManualValue = field(default_factory=ManualValue)
    hole_diameter_mm: float | None = None; design_horizon: str = ""; design_bench_height_m: float | None = None
    bench_face_angle_deg: float | None = None; block_width_m: float | None = None; total_hole_count: int = 0
    total_drilling_length_m: ManualValue = field(default_factory=ManualValue)
    total_explosive_mass_kg: float | None = None; rock_yield_m3_per_drilling_m: float | None = None
    specific_drilling_m_per_m3: float | None = None; powder_factor_kg_per_m3: float | None = None

    def recalculate(self, groups: list[BlastDrillingGroup]) -> None:
        self.average_depth_without_subdrill_m = max((self.average_hole_depth_m or 0) - (self.subdrill_m or 0), 0)
        area = self.drilling_area_m2.accepted_value
        self.block_volume_m3.calculated_value = area * self.design_bench_height_m if area is not None and self.design_bench_height_m is not None else None
        included = [g for g in groups if g.included]
        self.total_hole_count = sum(g.hole_count or 0 for g in included)
        lengths = [g.drilling_length() for g in included]
        self.total_drilling_length_m.calculated_value = None if any(x is None for x in lengths) else sum(lengths)
        masses = [group.total_explosive_mass() for group in included]
        self.total_explosive_mass_kg = None if any(value is None for value in masses) else sum(masses)
        volume, length = self.block_volume_m3.accepted_value, self.total_drilling_length_m.accepted_value
        self.rock_yield_m3_per_drilling_m = _ratio(volume, length)
        self.specific_drilling_m_per_m3 = _ratio(length, volume)
        self.powder_factor_kg_per_m3 = _ratio(self.total_explosive_mass_kg, volume)


@dataclass
class ContourParameters:
    controlled_blasting_method: str = ""; custom_method_name: str = ""
    design_limit_offset_m: float | None = None; line_length_m: float | None = None; hole_count: int | None = None
    average_spacing_m: float | None = None; average_depth_m: float | None = None; diameter_mm: float | None = None
    inclination_deg: float | None = None; subdrill_m: float | None = None; toe_standoff_m: float | None = None
    buffer_burden_m: float | None = None; row_count: int | None = None
    delay_relative_to_production_ms: float | None = None; charge_construction_text: str = ""
    explosive_type: str = ""; charge_concentration_kg_per_m: float | None = None
    decoupled_charge: bool = False; unloaded_holes: bool = False; notes: str = ""

    def set_method(self, method: str) -> None:
        if method not in CONTROLLED_BLASTING_METHODS: raise ValueError("Unsupported controlled blasting method")
        self.controlled_blasting_method = method
        self.unloaded_holes = method == "line_drilling"
        self.decoupled_charge = method in {"presplit", "midsplit"}


@dataclass
class ActualDrillingGroup:
    """Frozen, editable execution snapshot; never holds a design object reference."""
    id: str = field(default_factory=lambda: _new_id("AG")); design_group_id: str | None = None
    group_type: str = "main_pattern"; custom_type_name: str = ""; name: str = ""; sequence_order: int = 1
    included: bool = True; copied_from_design: bool = False
    copied_from_technical_revision_id: str | None = None; copied_at: str | None = None
    hole_count: int | None = None; diameter_mm: float | None = None; average_depth_m: float | None = None
    subdrill_m: float | None = None; burden_m: float | None = None; spacing_m: float | None = None
    row_count: int | None = None; inclination_deg: float | None = None; azimuth_deg: float | None = None
    line_offset_m: float | None = None; toe_standoff_m: float | None = None; stemming_length_m: float | None = None
    charge_mass_per_hole_kg: float | None = None; charge_concentration_kg_per_m: float | None = None
    total_charge_mass_kg: float | None = None; explosive_type: str = ""; charge_construction_text: str = ""
    initiation_sequence: str = ""; delay_ms: float | None = None; drilling_length_m: float | None = None
    air_deck_count: int | None = None; deck_notes: str = ""; charge_decks: list[dict[str, Any]] = field(default_factory=list)
    rejected_hole_count: int | None = None; redrilled_hole_count: int | None = None
    wet_hole_count: int | None = None; uncharged_hole_count: int | None = None
    mean_collar_deviation_m: float | None = None; max_collar_deviation_m: float | None = None
    mean_toe_deviation_m: float | None = None; max_toe_deviation_m: float | None = None
    deviations_text: str = ""; notes: str = ""
    charge_components: list[ChargeComponent] = field(default_factory=list)

    def __post_init__(self):
        for name in ("mean_collar_deviation_m", "max_collar_deviation_m",
                     "mean_toe_deviation_m", "max_toe_deviation_m"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and non-negative")

    def effective_drilling_length(self):
        if not self.included: return 0.0
        return None if self.hole_count is None or self.average_depth_m is None else self.hole_count * self.average_depth_m

    def effective_charge_mass(self):
        if not self.included: return 0.0
        per_hole = self.explosive_mass_per_hole_kg()
        return None if per_hole is None or self.hole_count is None else per_hole * self.hole_count

    def explosive_mass_per_hole_kg(self):
        if not self.charge_components: return 0.0
        try: return sum(component_explosive_mass_kg(item, self.diameter_mm) for item in self.charge_components)
        except ValueError: return None

    def stemming_total_m(self) -> float:
        """Current factual stemming derived only from factual charge components."""
        return sum(item.length_m for item in self.charge_components if item.kind is ChargeComponentKind.STEMMING)

    def charge_matches(self, design: BlastDrillingGroup | None) -> bool:
        return design is not None and charge_engineering_content(self.charge_components) == charge_engineering_content(design.charge_components)

    @classmethod
    def from_design(cls, group: BlastDrillingGroup, revision_id: str | None = None):
        target = cls(design_group_id=group.id, copied_from_design=True,
                     copied_from_technical_revision_id=revision_id, copied_at=utc_now().isoformat())
        for name in _DESIGN_COPY_FIELDS:
            setattr(target, name, deepcopy(getattr(group, name)))
        # The compatibility scalar is intentionally not copied: factual length
        # always follows the editable factual hole count and depth.
        target.drilling_length_m = None
        target.charge_mass_per_hole_kg = None
        target.total_charge_mass_kg = None
        target.stemming_length_m = group.stemming_total_m()
        target.explosive_type = group.explosive_names()
        target.charge_components = deepcopy(group.charge_components)
        return target


_DESIGN_COPY_FIELDS = ("group_type", "custom_type_name", "name", "sequence_order", "included", "hole_count",
    "diameter_mm", "average_depth_m", "subdrill_m", "burden_m", "spacing_m", "row_count", "inclination_deg",
    "azimuth_deg", "line_offset_m", "toe_standoff_m", "initiation_sequence", "delay_ms")


def charge_engineering_content(components: list[ChargeComponent]) -> tuple:
    """Canonical charge content comparison, deliberately excluding component UUIDs."""
    def snapshot_value(snapshot):
        if snapshot is None: return None
        return tuple(getattr(snapshot, item.name) for item in fields(ExplosiveProductSnapshot))
    return tuple((component.kind, component.start_depth_m, component.end_depth_m,
                  component.cartridge_pitch_m, snapshot_value(component.product_snapshot))
                 for component in components)


@dataclass
class ActualExecution:
    actual_drilling_groups: list[ActualDrillingGroup] = field(default_factory=list)
    actual_blast_date: str | None = None; actual_drilling_area_m2: float | None = None
    actual_block_volume_m3: float | None = None; actual_total_hole_count: int | None = None
    actual_total_drilling_length_m: float | None = None; actual_total_explosive_mass_kg: float | None = None
    actual_average_depth_m: float | None = None; actual_rock_yield_m3_per_drilling_m: float | None = None
    actual_specific_drilling_m_per_m3: float | None = None; actual_powder_factor_kg_per_m3: float | None = None
    rejected_hole_count: int | None = None; redrilled_hole_count: int | None = None
    wet_hole_count: int | None = None; uncharged_hole_count: int | None = None
    execution_notes: str = ""; deviations_text: str = ""; completion_status: str = "planned"
    migration_warnings: list[str] = field(default_factory=list)

    # Aliases retained for callers using the PR #30 names.
    @property
    def actual_hole_count(self): return self.actual_total_hole_count
    @actual_hole_count.setter
    def actual_hole_count(self, value): self.actual_total_hole_count = value
    @property
    def actual_drilling_length_m(self): return self.actual_total_drilling_length_m
    @actual_drilling_length_m.setter
    def actual_drilling_length_m(self, value): self.actual_total_drilling_length_m = value

    def recalculate(self, *, geometry_area_m2: float | None = None, production: bool = False):
        """Rebuild every factual indicator from included factual groups."""
        groups = [g for g in self.actual_drilling_groups if g.included]
        self.actual_total_hole_count = sum(g.hole_count or 0 for g in groups)
        lengths = [g.effective_drilling_length() for g in groups]
        masses = [g.effective_charge_mass() for g in groups]
        self.actual_total_drilling_length_m = None if any(v is None for v in lengths) else sum(lengths)
        self.actual_total_explosive_mass_kg = None if any(v is None for v in masses) else sum(masses)
        self.actual_average_depth_m = _ratio(self.actual_total_drilling_length_m, self.actual_total_hole_count)
        if production:
            self.actual_drilling_area_m2 = geometry_area_m2
            self.actual_block_volume_m3 = (geometry_area_m2 * self.actual_average_depth_m
                if geometry_area_m2 is not None and self.actual_average_depth_m is not None else None)
        else:
            self.actual_drilling_area_m2 = None; self.actual_block_volume_m3 = None
        volume, length = self.actual_block_volume_m3, self.actual_total_drilling_length_m
        self.actual_rock_yield_m3_per_drilling_m = _ratio(volume, length)
        self.actual_specific_drilling_m_per_m3 = _ratio(length, volume)
        self.actual_powder_factor_kg_per_m3 = _ratio(self.actual_total_explosive_mass_kg, volume)
        self.rejected_hole_count = sum(g.rejected_hole_count or 0 for g in groups)
        self.redrilled_hole_count = sum(g.redrilled_hole_count or 0 for g in groups)
        self.wet_hole_count = sum(g.wet_hole_count or 0 for g in groups)
        self.uncharged_hole_count = sum(g.uncharged_hole_count or 0 for g in groups)

    def copy_from_design(self, groups, revision_id=None, mode="fill_empty"):
        if mode not in {"fill_empty", "add_missing", "replace"}: raise ValueError("Unsupported copy mode")
        if mode == "replace":
            previous = {g.design_group_id: g for g in self.actual_drilling_groups if g.design_group_id}
            self.actual_drilling_groups = [ActualDrillingGroup.from_design(g, revision_id) for g in groups]
            for actual in self.actual_drilling_groups:
                old = previous.get(actual.design_group_id)
                if old:
                    for name in ("mean_collar_deviation_m", "max_collar_deviation_m", "mean_toe_deviation_m", "max_toe_deviation_m"):
                        setattr(actual, name, getattr(old, name))
        else:
            by_design = {g.design_group_id: g for g in self.actual_drilling_groups if g.design_group_id}
            for design in groups:
                current = by_design.get(design.id)
                if current is None:
                    self.actual_drilling_groups.append(ActualDrillingGroup.from_design(design, revision_id)); continue
                if mode == "fill_empty": self.copy_one(design, current, revision_id, "fill_empty")
        self.recalculate()

    def copy_one(self, design, actual=None, revision_id=None, mode="fill_empty"):
        fresh = ActualDrillingGroup.from_design(design, revision_id)
        if actual is None:
            self.actual_drilling_groups.append(fresh); return fresh
        if mode == "replace":
            index = self.actual_drilling_groups.index(actual); fresh.id = actual.id
            self.actual_drilling_groups[index] = fresh; return fresh
        for name in _DESIGN_COPY_FIELDS:
            if getattr(actual, name) in (None, "", []): setattr(actual, name, deepcopy(getattr(fresh, name)))
        actual.design_group_id = design.id
        return actual

    def completion_warnings(self):
        if self.completion_status != "completed": return []
        warnings = []
        if not self.actual_drilling_groups: warnings.append("Нет фактических групп")
        if not self.actual_blast_date: warnings.append("Не указана фактическая дата взрыва")
        if not self.actual_total_hole_count: warnings.append("Не указано число фактических скважин")
        if not self.actual_total_drilling_length_m: warnings.append("Не указан фактический метраж бурения")
        return warnings


@dataclass
class BlastEventTechnicalCardRevision:
    id: str; technical_card_id: str; revision_number: int; created_at: datetime
    geometry_revision_id: str; event_type: str; status: str; common_parameters: CommonParameters
    drilling_groups: list[BlastDrillingGroup]; production_parameters: ProductionParameters | None = None
    contour_parameters: ContourParameters | None = None; geomechanical_parameters: GeomechanicalParameters | None = None
    actual_execution: ActualExecution = field(default_factory=ActualExecution); notes: str = ""
    author: str | None = None; change_reason: str = ""
    design_slope_orientation: DesignSlopeOrientation = field(default_factory=DesignSlopeOrientation)

    def validate_completion(self) -> list[str]:
        errors = []
        if not self.drilling_groups: errors.append("Добавьте группу бурения")
        if self.event_type == "production" and (not self.geomechanical_parameters or not self.geomechanical_parameters.minimum_complete()):
            errors.append("Заполните минимальное геомеханическое описание")
        if self.event_type == "contour" and not (self.contour_parameters and self.contour_parameters.controlled_blasting_method):
            errors.append("Выберите метод контурного взрывания")
        return errors

    def comparison_rows(self):
        """Return reproducible project/fact rows for the UI and exports."""
        actual_by_design = {g.design_group_id: g for g in self.actual_execution.actual_drilling_groups if g.design_group_id}
        specs = (("hole_count", "Скважины", "шт"), ("diameter_mm", "Диаметр", "мм"),
            ("average_depth_m", "Средняя глубина", "м"), ("subdrill_m", "Перебур", "м"),
            ("burden_m", "ЛНС / расстояние между рядами", "м"), ("spacing_m", "Шаг скважин в ряду", "м"),
            ("drilling_length", "Метраж бурения", "м"), ("charge_mass_per_hole_kg", "Масса заряда на скважину", "кг"),
            ("total_charge_mass_kg", "Общая масса заряда", "кг"), ("stemming_length_m", "Забойка", "м"),
            ("delay_ms", "Замедление", "мс"))
        rows = []
        for design in self.drilling_groups:
            actual = actual_by_design.get(design.id)
            for attr, label, unit in specs:
                if attr == "drilling_length": project = design.drilling_length()
                elif attr == "charge_mass_per_hole_kg": project = design.explosive_mass_per_hole_kg()
                elif attr == "total_charge_mass_kg": project = design.total_explosive_mass()
                elif attr == "stemming_length_m": project = design.stemming_total_m()
                else: project = getattr(design, attr)
                fact = actual.effective_drilling_length() if actual and attr == "drilling_length" else (getattr(actual, attr) if actual else None)
                rows.append(comparison_value(design.name, label, unit, project, fact))
        included = [g for g in self.drilling_groups if g.included]
        project_holes = sum(g.hole_count or 0 for g in included)
        lengths = [g.drilling_length() for g in included]
        project_length = None if any(v is None for v in lengths) else sum(lengths)
        masses = [g.total_explosive_mass() for g in included]
        project_mass = None if any(v is None for v in masses) else sum(masses)
        production = self.production_parameters
        project_volume = production.block_volume_m3.accepted_value if production else None
        totals = (("Всего скважин", "шт", project_holes, self.actual_execution.actual_total_hole_count),
            ("Общий метраж бурения", "м", project_length, self.actual_execution.actual_total_drilling_length_m),
            ("Общая масса ВВ", "кг", project_mass, self.actual_execution.actual_total_explosive_mass_kg),
            ("Объём", "м³", project_volume, self.actual_execution.actual_block_volume_m3),
            ("Выход горной массы", "м³/м", production.rock_yield_m3_per_drilling_m if production else None, self.actual_execution.actual_rock_yield_m3_per_drilling_m),
            ("Удельное бурение", "м/м³", production.specific_drilling_m_per_m3 if production else None, self.actual_execution.actual_specific_drilling_m_per_m3),
            ("Удельный расход ВВ", "кг/м³", production.powder_factor_kg_per_m3 if production else None, self.actual_execution.actual_powder_factor_kg_per_m3))
        rows.extend(comparison_value("ИТОГО", label, unit, project, actual) for label, unit, project, actual in totals)
        return rows

    def compact_design_actual(self, design_group_id: str) -> list[dict[str, Any]]:
        """Comparable engineering values matched only by the stable design group id."""
        design = next((g for g in self.drilling_groups if g.id == design_group_id), None)
        actual = next((g for g in self.actual_execution.actual_drilling_groups
                       if g.design_group_id == design_group_id), None)
        specs = (("burden_m", "Burden"), ("spacing_m", "Spacing"),
                 ("stemming_length_m", "Stemming"), ("charge_mass_per_hole_kg", "Charge mass per hole"),
                 ("average_depth_m", "Average depth"), ("subdrill_m", "Subdrill"),
                 ("inclination_deg", "Inclination"), ("azimuth_deg", "Azimuth"))
        rows = []
        for attr, label in specs:
            if design is None:
                planned = None
            elif attr == "stemming_length_m":
                planned = design.stemming_total_m()
            elif attr == "charge_mass_per_hole_kg":
                planned = design.explosive_mass_per_hole_kg()
            else:
                planned = getattr(design, attr)
            if actual is None:
                factual = None
            elif attr == "stemming_length_m":
                factual = actual.stemming_total_m()
            elif attr == "charge_mass_per_hole_kg":
                factual = actual.explosive_mass_per_hole_kg()
            else:
                factual = getattr(actual, attr)
            delta = None
            if planned is not None and factual is not None:
                raw = factual - planned
                delta = ((raw + 180) % 360) - 180 if attr == "azimuth_deg" else raw
            rows.append({"parameter": label, "design": planned, "actual": factual, "delta": delta})
        return rows

    def engineering_ratios(self, design_group_id: str) -> dict[str, float | None]:
        actual = next((g for g in self.actual_execution.actual_drilling_groups
                       if g.design_group_id == design_group_id), None)
        burden = actual.burden_m if actual else None
        spacing = actual.spacing_m if actual else None
        toe = actual.mean_toe_deviation_m if actual else None
        bench = self.production_parameters.design_bench_height_m if self.production_parameters else None
        return {"B/S": _positive_ratio(burden, spacing), "S/B": _positive_ratio(spacing, burden),
                "H/B": _positive_ratio(bench, burden),
                "mean toe deviation / burden": _positive_ratio(toe, burden),
                "mean toe deviation / spacing": _positive_ratio(toe, spacing)}


def comparison_value(group, parameter, unit, project, actual):
    absolute = actual - project if actual is not None and project is not None else None
    relative = absolute / project * 100 if absolute is not None and project not in (None, 0) else None
    return {"group": group, "parameter": parameter, "unit": unit, "project": project, "actual": actual,
            "absolute_deviation": absolute, "relative_deviation_percent": relative}


def _positive_ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator <= 0:
        return None
    value = numerator / denominator
    return value if isfinite(value) else None


@dataclass
class BlastEventTechnicalCard:
    id: str; blast_event_id: str; revisions: list[BlastEventTechnicalCardRevision] = field(default_factory=list)
    active_revision_id: str | None = None; is_archived: bool = False

    def active_revision(self):
        return next((r for r in self.revisions if r.id == self.active_revision_id), None)

    def save_revision(self, draft: BlastEventTechnicalCardRevision, *, status="draft", change_reason=""):
        saved = deepcopy(draft); number = len(self.revisions) + 1
        if saved.geomechanical_parameters:
            saved.geomechanical_parameters.__post_init__()
            for joint_set in saved.geomechanical_parameters.joint_sets: joint_set.__post_init__()
        for actual_group in saved.actual_execution.actual_drilling_groups: actual_group.__post_init__()
        saved.id = f"{self.id}-R{number:03d}"; saved.technical_card_id = self.id
        saved.revision_number = number; saved.created_at = utc_now(); saved.status = status; saved.change_reason = change_reason
        if status == "completed" and saved.validate_completion(): raise ValueError("; ".join(saved.validate_completion()))
        if saved.production_parameters: saved.production_parameters.recalculate(saved.drilling_groups)
        area = (saved.production_parameters.drilling_area_m2.calculated_value
                if saved.production_parameters else None)
        saved.actual_execution.recalculate(
            geometry_area_m2=area, production=saved.event_type == "production")
        self.revisions.append(saved); self.active_revision_id = saved.id
        return saved

    def remove_group(self, revision, group_id):
        group = next(g for g in revision.drilling_groups if g.id == group_id)
        if group.group_type == "main_pattern" and sum(g.group_type == "main_pattern" for g in revision.drilling_groups) == 1:
            raise ValueError("Нельзя удалить последнюю основную сеть")
        revision.drilling_groups.remove(group)

    def to_dict(self): return _encode(self)

    @classmethod
    def from_dict(cls, data): return _card_from_dict(data)


def new_technical_card(event: BlastEvent) -> tuple[BlastEventTechnicalCard, BlastEventTechnicalCardRevision]:
    geometry = event.active_geometry_revision()
    if geometry is None: raise ValueError("BlastEvent has no active geometry revision")
    card = BlastEventTechnicalCard(_new_id("TC"), event.id)
    common = CommonParameters(blast_date=event.event_date.isoformat() if event.event_date else None,
        block_name=event.name, working_horizon=event.elevation, source_geometry_revision_id=geometry.id,
        source_csv=geometry.source_file_name)
    production = ProductionParameters() if event.event_type == "production" else None
    if production and isinstance(geometry.plan_geometry, PlanPolygon): production.drilling_area_m2.calculated_value = polygon_area_m2(geometry.plan_geometry)
    contour = ContourParameters() if event.event_type == "contour" else None
    groups = [BlastDrillingGroup(group_type="main_pattern", name="Основная сеть")] if production else [BlastDrillingGroup(group_type="contour_line", name="Контурный ряд")]
    revision = BlastEventTechnicalCardRevision("", card.id, 0, utc_now(), geometry.id, event.event_type, "draft", common, groups,
        production, contour, GeomechanicalParameters() if production else None)
    return card, revision


class TechnicalCardService:
    def __init__(self, state): self.state = state
    def card_for_event(self, event_id): return next((c for c in self.state.technical_cards if c.blast_event_id == event_id), None)
    def edit_or_create(self, event: BlastEvent):
        card = self.card_for_event(event.id)
        if card and card.active_revision(): return card, deepcopy(card.active_revision())
        if card:
            fresh, revision = new_technical_card(event); revision.technical_card_id = card.id
            return card, revision
        card, revision = new_technical_card(event); self.state.technical_cards.append(card); return card, revision


def _encode(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, float) and not isfinite(value): return None
    if isinstance(value, BlastDrillingGroup):
        legacy = {"legacy_actual_drilling_length_m", "charge_decks", "explosive_type", "charge_mass_per_hole_kg",
            "charge_concentration_kg_per_m", "total_charge_mass_kg", "stemming_length_m",
            "charge_construction_text", "air_deck_count", "deck_notes", "planned_drilling_length_m"}
        return {f.name: _encode(getattr(value, f.name)) for f in fields(value) if f.name not in legacy}
    if isinstance(value, GeomechanicalParameters):
        return {f.name: _encode(getattr(value, f.name)) for f in fields(value) if f.name != "q_value"}
    if hasattr(value, "__dataclass_fields__"): return {f.name: _encode(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict): return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, list): return [_encode(v) for v in value]
    return value


def _construct(cls, data):
    return cls(**{f.name: data[f.name] for f in fields(cls) if f.name in data})


def _charge_component_from_dict(data):
    raw = dict(data); snapshot = raw.get("product_snapshot")
    if snapshot:
        snapshot = dict(snapshot)
        snapshot["kind"] = ExplosiveProductKind(snapshot["kind"])
        from domain.blasting.charge_design import ChargeForm
        if snapshot.get("charge_form") is not None: snapshot["charge_form"] = ChargeForm(snapshot["charge_form"])
        snapshot["explosive_class"] = ExplosiveClass(snapshot.get("explosive_class", "other"))
        raw["product_snapshot"] = _construct(ExplosiveProductSnapshot, snapshot)
    raw["kind"] = ChargeComponentKind(raw["kind"])
    return _construct(ChargeComponent, raw)


def _geomechanics_from_dict(data):
    """Read the canonical payload, conservatively falling back to representatives."""
    migrated = dict(data)
    if "ucs_mpa" not in migrated:
        migrated["ucs_mpa"] = migrated.get("representative_ucs_mpa")
    if "rqd_percent" not in migrated:
        migrated["rqd_percent"] = migrated.get("rqd_representative_percent")
    if "notes" not in migrated:
        migrated["notes"] = migrated.get("geomechanical_notes", "")
    # PR #113 briefly allowed free-form Barton ratings. Treat those disposable
    # development payload values as missing rather than making an old draft
    # impossible to open after the canonical rating validation lands.
    for name, allowed in (
        ("jn", BARTON_JN_VALUES), ("jr", BARTON_JR_VALUES),
        ("ja", BARTON_JA_VALUES), ("jw", BARTON_JW_VALUES),
    ):
        value = migrated.get(name)
        if value is not None and (not isfinite(value) or not _is_allowed_rating(value, allowed)):
            migrated[name] = None
    if migrated.get("gsi") is not None and not 1 <= migrated["gsi"] <= 100:
        migrated["gsi"] = None
    if migrated.get("ff") is not None and migrated["ff"] < 0:
        migrated["ff"] = None
    migrated["joint_sets"] = [
        item if isinstance(item, JointSetOrientation) else _construct(JointSetOrientation, item)
        for item in migrated.get("joint_sets", [])
    ]
    return _construct(GeomechanicalParameters, migrated)


def _card_from_dict(d):
    card = BlastEventTechnicalCard(d["id"], d["blast_event_id"], active_revision_id=d.get("active_revision_id"), is_archived=d.get("is_archived", False))
    for x in d.get("revisions", []):
        prod = _construct(ProductionParameters, x["production_parameters"]) if x.get("production_parameters") else None
        if prod:
            prod.drilling_area_m2 = _construct(ManualValue, x["production_parameters"].get("drilling_area_m2", {}))
            prod.block_volume_m3 = _construct(ManualValue, x["production_parameters"].get("block_volume_m3", {}))
            prod.total_drilling_length_m = _construct(ManualValue, x["production_parameters"].get("total_drilling_length_m", {}))
        raw_groups = x.get("drilling_groups", [])
        groups = []
        for raw in raw_groups:
            migrated = dict(raw)
            migrated["charge_components"] = [_charge_component_from_dict(item) for item in migrated.get("charge_components", [])]
            legacy = migrated.pop("actual_drilling_length_m", None)
            group = _construct(BlastDrillingGroup, migrated); group.legacy_actual_drilling_length_m = legacy; groups.append(group)
        raw_actual = dict(x.get("actual_execution", {}))
        # PR #30 summary aliases.
        if "actual_hole_count" in raw_actual and "actual_total_hole_count" not in raw_actual:
            raw_actual["actual_total_hole_count"] = raw_actual["actual_hole_count"]
        if "actual_drilling_length_m" in raw_actual and "actual_total_drilling_length_m" not in raw_actual:
            raw_actual["actual_total_drilling_length_m"] = raw_actual["actual_drilling_length_m"]
        raw_actual.pop("actual_hole_count", None); raw_actual.pop("actual_drilling_length_m", None)
        actual_group_data = raw_actual.pop("actual_drilling_groups", [])
        actual = _construct(ActualExecution, raw_actual)
        actual.actual_drilling_groups = []
        for raw_group in actual_group_data:
            migrated_group = dict(raw_group)
            migrated_group["charge_components"] = [
                _charge_component_from_dict(item) for item in migrated_group.get("charge_components", [])
            ]
            actual.actual_drilling_groups.append(_construct(ActualDrillingGroup, migrated_group))
        for group in groups:
            if group.legacy_actual_drilling_length_m is None: continue
            target = next((g for g in actual.actual_drilling_groups if g.design_group_id == group.id), None)
            if target is None:
                target = ActualDrillingGroup.from_design(group, x.get("id")); actual.actual_drilling_groups.append(target)
            if target.drilling_length_m is None or not actual_group_data: target.drilling_length_m = group.legacy_actual_drilling_length_m
            actual.migration_warnings.append(f"Перенесён старый фактический метраж группы «{group.name}»")
        if actual.actual_drilling_groups:
            area = prod.drilling_area_m2.calculated_value if prod else None
            actual.recalculate(geometry_area_m2=area, production=x["event_type"] == "production")
        card.revisions.append(BlastEventTechnicalCardRevision(
            id=x["id"], technical_card_id=x["technical_card_id"], revision_number=x["revision_number"],
            created_at=datetime.fromisoformat(x["created_at"]), geometry_revision_id=x["geometry_revision_id"],
            event_type=x["event_type"], status=x["status"], common_parameters=_construct(CommonParameters, x["common_parameters"]),
            drilling_groups=groups,
            production_parameters=prod, contour_parameters=_construct(ContourParameters, x["contour_parameters"]) if x.get("contour_parameters") else None,
            geomechanical_parameters=_geomechanics_from_dict(x["geomechanical_parameters"]) if x.get("geomechanical_parameters") else None,
            actual_execution=actual, notes=x.get("notes", ""), author=x.get("author"), change_reason=x.get("change_reason", ""),
            design_slope_orientation=_construct(DesignSlopeOrientation, x.get("design_slope_orientation", {}))))
    return card
