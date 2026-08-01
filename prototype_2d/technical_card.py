"""Versioned engineering cards attached to stable BlastEvent identifiers."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from math import isfinite
from typing import Any
from uuid import uuid4

from .domain import AssessmentDomainState, BlastEvent, PlanPolygon, utc_now

PRODUCTION_GROUP_TYPES = {
    "main_pattern": "Основная сеть", "inner_buffer": "Внутренний буферный ряд",
    "outer_buffer": "Внешний буферный ряд", "buffer": "Буферные скважины",
    "cut_opening": "Врубовые / разрезные скважины", "crest": "Бровочные скважины",
    "toe": "Подошвенные скважины", "relief": "Разгрузочные скважины",
    "auxiliary": "Вспомогательные скважины", "other": "Другой тип",
}
CONTOUR_GROUP_TYPES = {
    "contour_line": "Контурный ряд", "presplit_line": "Presplit ряд",
    "midsplit_line": "Midsplit ряд", "postsplit_line": "Postsplit ряд",
    "line_drilling": "Линия незаряженных скважин", "inner_buffer": "Внутренний буферный ряд",
    "outer_buffer": "Внешний буферный ряд", "trim_row": "Trim ряд", "other": "Другой тип",
}
CONTROLLED_BLASTING_METHODS = {
    "buffer_cushion": "Буферное / cushion blasting", "trim": "Оконтуривающее / trim blasting",
    "presplit": "Предварительное щелеобразование / presplit",
    "midsplit": "Промежуточное щелеобразование / midsplit",
    "postsplit": "Последующее щелеобразование / postsplit",
    "line_drilling": "Бурение по линии незаряженных скважин", "other": "Другой метод",
}

def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"

def polygon_area_m2(polygon: PlanPolygon | None) -> float | None:
    """Shoelace area in domain X/Y coordinates (never scene coordinates)."""
    if polygon is None:
        return None
    return abs(sum(a.x * b.y - b.x * a.y for a, b in zip(polygon.ring, polygon.ring[1:]))) / 2

def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / denominator
    return value if isfinite(value) else None

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
class GeomechanicalParameters:
    lithology: str = ""; geotechnical_domain: str = ""; rock_strength_class_text: str = ""
    representative_ucs_mpa: float | None = None; ucs_min_mpa: float | None = None; ucs_max_mpa: float | None = None
    rqd_min_percent: float | None = None; rqd_max_percent: float | None = None
    rqd_representative_percent: float | None = None; rock_mass_properties_text: str = ""
    fracturing_description: str = ""; water_condition: str = ""; geomechanical_notes: str = ""

    def minimum_complete(self) -> bool:
        strength = bool(self.rock_strength_class_text.strip()) or self.representative_ucs_mpa is not None
        rqd = any(x is not None for x in (self.rqd_min_percent, self.rqd_max_percent, self.rqd_representative_percent))
        return strength and (rqd or bool(self.rock_mass_properties_text.strip()))

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
    initiation_sequence: str = ""; delay_ms: float | None = None; actual_drilling_length_m: float | None = None
    air_deck_count: int | None = None; deck_notes: str = ""; charge_decks: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def drilling_length(self) -> float | None:
        if not self.included: return 0.0
        if self.actual_drilling_length_m is not None: return self.actual_drilling_length_m
        if self.hole_count is None or self.average_depth_m is None: return None
        return self.hole_count * self.average_depth_m

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
class ActualExecution:
    actual_blast_date: str | None = None; actual_drilling_area_m2: float | None = None
    actual_drilling_length_m: float | None = None; actual_hole_count: int | None = None
    actual_total_explosive_mass_kg: float | None = None; actual_average_depth_m: float | None = None
    rejected_hole_count: int | None = None; redrilled_hole_count: int | None = None
    execution_notes: str = ""; deviations_text: str = ""; completion_status: str = "planned"

@dataclass
class BlastEventTechnicalCardRevision:
    id: str; technical_card_id: str; revision_number: int; created_at: datetime
    geometry_revision_id: str; event_type: str; status: str; common_parameters: CommonParameters
    drilling_groups: list[BlastDrillingGroup]; production_parameters: ProductionParameters | None = None
    contour_parameters: ContourParameters | None = None; geomechanical_parameters: GeomechanicalParameters | None = None
    actual_execution: ActualExecution = field(default_factory=ActualExecution); notes: str = ""
    author: str | None = None; change_reason: str = ""

    def validate_completion(self) -> list[str]:
        errors = []
        if not self.drilling_groups: errors.append("Добавьте группу бурения")
        if self.event_type == "production" and (not self.geomechanical_parameters or not self.geomechanical_parameters.minimum_complete()):
            errors.append("Заполните минимальное геомеханическое описание")
        if self.event_type == "contour" and not (self.contour_parameters and self.contour_parameters.controlled_blasting_method):
            errors.append("Выберите метод контурного взрывания")
        return errors

@dataclass
class BlastEventTechnicalCard:
    id: str; blast_event_id: str; revisions: list[BlastEventTechnicalCardRevision] = field(default_factory=list)
    active_revision_id: str | None = None; is_archived: bool = False

    def active_revision(self):
        return next((r for r in self.revisions if r.id == self.active_revision_id), None)

    def save_revision(self, draft: BlastEventTechnicalCardRevision, *, status="draft", change_reason=""):
        saved = deepcopy(draft); number = len(self.revisions) + 1
        saved.id = f"{self.id}-R{number:03d}"; saved.technical_card_id = self.id
        saved.revision_number = number; saved.created_at = utc_now(); saved.status = status; saved.change_reason = change_reason
        if status == "completed" and saved.validate_completion(): raise ValueError("; ".join(saved.validate_completion()))
        if saved.production_parameters: saved.production_parameters.recalculate(saved.drilling_groups)
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
    def __init__(self, state: AssessmentDomainState): self.state = state
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
    if hasattr(value, "__dataclass_fields__"): return {k: _encode(v) for k, v in asdict(value).items()}
    if isinstance(value, dict): return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, list): return [_encode(v) for v in value]
    return value

def _construct(cls, data):
    return cls(**{f.name: data[f.name] for f in fields(cls) if f.name in data})

def _card_from_dict(d):
    card = BlastEventTechnicalCard(d["id"], d["blast_event_id"], active_revision_id=d.get("active_revision_id"), is_archived=d.get("is_archived", False))
    for x in d.get("revisions", []):
        prod = _construct(ProductionParameters, x["production_parameters"]) if x.get("production_parameters") else None
        if prod:
            prod.drilling_area_m2 = _construct(ManualValue, x["production_parameters"].get("drilling_area_m2", {}))
            prod.block_volume_m3 = _construct(ManualValue, x["production_parameters"].get("block_volume_m3", {}))
            prod.total_drilling_length_m = _construct(ManualValue, x["production_parameters"].get("total_drilling_length_m", {}))
        card.revisions.append(BlastEventTechnicalCardRevision(
            id=x["id"], technical_card_id=x["technical_card_id"], revision_number=x["revision_number"],
            created_at=datetime.fromisoformat(x["created_at"]), geometry_revision_id=x["geometry_revision_id"],
            event_type=x["event_type"], status=x["status"], common_parameters=_construct(CommonParameters, x["common_parameters"]),
            drilling_groups=[_construct(BlastDrillingGroup, g) for g in x.get("drilling_groups", [])],
            production_parameters=prod, contour_parameters=_construct(ContourParameters, x["contour_parameters"]) if x.get("contour_parameters") else None,
            geomechanical_parameters=_construct(GeomechanicalParameters, x["geomechanical_parameters"]) if x.get("geomechanical_parameters") else None,
            actual_execution=_construct(ActualExecution, x.get("actual_execution", {})), notes=x.get("notes", ""), author=x.get("author"), change_reason=x.get("change_reason", "")))
    return card
