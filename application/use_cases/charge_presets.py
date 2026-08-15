from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ChargeDesignPreset, ExplosiveProduct,
    ExplosiveProductKind, apply_preset, preset_components,
)


class ChargePresets:
    def __init__(self, persistence, *, site_id: int, can_edit: bool):
        self._persistence, self.site_id, self.can_edit = persistence, site_id, can_edit

    def list_presets(self) -> list[ChargeDesignPreset]: return self._persistence.list_presets(self.site_id)
    def _editable(self):
        if not self.can_edit: raise PermissionError("Charge presets are read-only")
    @staticmethod
    def _name(name):
        value=name.strip()
        if not value: raise ValueError("Charge preset name is required")
        if len(value)>255: raise ValueError("Charge preset name must not exceed 255 characters")
        return value
    @staticmethod
    def _reusable(components, products):
        current={product.id:product for product in products if product.enabled}
        for component in components:
            if component.kind is ChargeComponentKind.STEMMING: continue
            source_id=component.product_snapshot.source_product_id if component.product_snapshot else None
            product=current.get(source_id)
            expected=(ExplosiveProductKind.CARTRIDGE if component.kind is ChargeComponentKind.CARTRIDGE_EXPLOSIVE else ExplosiveProductKind.BULK)
            if product is None or product.kind is not expected:
                raise ValueError("Every explosive preset component must reference a current enabled catalogue product")
        return preset_components(components)
    def create(self, name: str, components: list[ChargeComponent], products: list[ExplosiveProduct]):
        self._editable(); return self._persistence.create_preset(self.site_id, self._name(name), self._reusable(components,products))
    def update(self, preset_id: int, name: str, components: list[ChargeComponent], products: list[ExplosiveProduct]):
        self._editable(); return self._persistence.update_preset(preset_id, self.site_id, self._name(name), self._reusable(components,products))
    def delete(self, preset_id: int): self._editable(); self._persistence.delete_preset(preset_id, self.site_id)
    def apply(self, preset: ChargeDesignPreset, products: list[ExplosiveProduct], hole_depth_m: float):
        if preset.site_id != self.site_id: raise PermissionError("Charge preset belongs to another Project")
        return apply_preset(preset.components, products, hole_depth_m)
