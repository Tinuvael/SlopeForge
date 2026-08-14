"""Project-scoped reusable templates for charge construction."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from domain.blasting.charge_design import (ChargeComponent, ChargeComponentKind,
    ExplosiveProduct, ExplosiveProductKind, validate_components)


@dataclass(frozen=True)
class ChargePresetComponent:
    kind: ChargeComponentKind
    start_depth_m: float
    end_depth_m: float
    source_product_id: int | None = None
    cartridge_pitch_m: float | None = None


@dataclass
class ChargeDesignPreset:
    id: int
    site_id: int
    name: str
    components: list[ChargePresetComponent] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Preset name is required")


def instantiate_preset(preset: ChargeDesignPreset, products: list[ExplosiveProduct],
                       hole_depth_m: float) -> list[ChargeComponent]:
    by_id = {product.id: product for product in products}
    result = []
    for specification in preset.components:
        product = None
        if specification.kind is not ChargeComponentKind.STEMMING:
            product = by_id.get(specification.source_product_id)
            if product is None or not product.enabled:
                raise ValueError("Preset references a missing or disabled explosive product")
            expected = (ExplosiveProductKind.BULK if specification.kind is ChargeComponentKind.BULK_EXPLOSIVE
                        else ExplosiveProductKind.CARTRIDGE)
            if product.kind is not expected:
                raise ValueError("Preset component kind does not match the explosive product")
        result.append(ChargeComponent(f"CC-{uuid4().hex}", specification.kind,
            specification.start_depth_m, specification.end_depth_m,
            product.snapshot() if product else None, specification.cartridge_pitch_m))
    validate_components(result, hole_depth_m)
    return result
