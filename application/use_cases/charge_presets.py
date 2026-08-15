from domain.blasting.charge_design import (
    ChargeComponent, ChargeDesignPreset, ExplosiveProduct, apply_preset, preset_components,
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
        return value
    def create(self, name: str, components: list[ChargeComponent]):
        self._editable(); return self._persistence.create_preset(self.site_id, self._name(name), preset_components(components))
    def update(self, preset_id: int, name: str, components: list[ChargeComponent]):
        self._editable(); return self._persistence.update_preset(preset_id, self.site_id, self._name(name), preset_components(components))
    def delete(self, preset_id: int): self._editable(); self._persistence.delete_preset(preset_id, self.site_id)
    def apply(self, preset: ChargeDesignPreset, products: list[ExplosiveProduct], hole_depth_m: float):
        if preset.site_id != self.site_id: raise PermissionError("Charge preset belongs to another Project")
        return apply_preset(preset.components, products, hole_depth_m)
