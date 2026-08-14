from dataclasses import replace
from application.ports.charge_presets import ChargePresetRepository
from domain.blasting.charge_presets import ChargeDesignPreset, instantiate_preset

class ChargePresets:
    def __init__(self, repository: ChargePresetRepository, catalogue, *, can_edit: bool):
        self.repository, self.catalogue, self.can_edit = repository, catalogue, can_edit
    def list(self, site_id): return self.repository.list_for_site(site_id)
    def _editable(self):
        if not self.can_edit: raise PermissionError("Charge presets are read-only for the current user")
    def create(self, preset): self._editable(); return self.repository.create(replace(preset, id=0))
    def update(self, preset): self._editable(); return self.repository.update(preset)
    def delete(self, preset_id, site_id): self._editable(); return self.repository.delete(preset_id, site_id)
    def instantiate(self, preset, hole_depth_m):
        return instantiate_preset(preset, self.catalogue.list_products(), hole_depth_m)
