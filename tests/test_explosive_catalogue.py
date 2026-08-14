from dataclasses import replace
from types import SimpleNamespace
import pytest

from application.errors import CatalogueConflictError
from application.use_cases.explosive_catalogue import ExplosiveCatalogue
from domain.blasting.charge_design import ExplosiveProduct, ExplosiveProductKind


class MemoryCatalogue:
    def __init__(self): self.items = {}; self.next_id = 1
    def list_products(self, *, enabled_only=False):
        return sorted((item for item in self.items.values() if item.enabled or not enabled_only),
                      key=lambda item: item.name)
    def get_product(self, product_id): return self.items.get(product_id)
    def create_product(self, product):
        if any(item.name == product.name for item in self.items.values()):
            raise CatalogueConflictError("An explosive product with this name already exists")
        product = replace(product, id=self.next_id); self.next_id += 1; self.items[product.id] = product
        return product
    def update_product(self, product): self.items[product.id] = product; return product
    def set_product_enabled(self, product_id, enabled):
        self.items[product_id] = replace(self.items[product_id], enabled=enabled)
        return self.items[product_id]


def product(name="Bulk", **changes):
    values = dict(id=0, name=name, kind=ExplosiveProductKind.BULK,
                  display_color="#123ABC", density_kg_m3=1000)
    values.update(changes); return ExplosiveProduct(**values)


def test_catalogue_create_list_update_disable_and_enable():
    adapter = MemoryCatalogue(); service = ExplosiveCatalogue(adapter, adapter, can_edit=True)
    assert service.list_products() == []
    bulk = service.create_product(product())
    cartridge = service.create_product(product(
        "Cartridge", kind=ExplosiveProductKind.CARTRIDGE, density_kg_m3=None,
        cartridge_diameter_mm=40, cartridge_mass_kg=.5, default_pitch_m=.25))
    assert [item.name for item in service.list_products()] == ["Bulk", "Cartridge"]
    bulk = service.update_product(replace(bulk, name="Bulk edited"))
    service.set_product_enabled(cartridge.id, False)
    assert service.list_products()[1].enabled is False
    assert service.list_enabled_products() == [bulk]
    service.set_product_enabled(cartridge.id, True)
    assert len(service.list_enabled_products()) == 2
    with pytest.raises(CatalogueConflictError): service.create_product(product("Bulk edited"))


def test_viewer_cannot_mutate_catalogue():
    adapter = MemoryCatalogue(); service = ExplosiveCatalogue(adapter, adapter, can_edit=False)
    assert service.list_products() == []
    with pytest.raises(PermissionError): service.create_product(product())


def test_update_revalidates_mutable_product_before_persistence():
    class TrackingCatalogue(MemoryCatalogue):
        update_called = False
        def update_product(self, submitted):
            self.update_called = True
            return super().update_product(submitted)

    adapter = TrackingCatalogue(); service = ExplosiveCatalogue(adapter, adapter, can_edit=True)
    submitted = product(); submitted.density_kg_m3 = None
    with pytest.raises(ValueError, match="Density"):
        service.update_product(submitted)
    assert adapter.update_called is False


@pytest.mark.parametrize("changes", [
    {"density_kg_m3": 0}, {"display_color": "red"},
    {"kind": ExplosiveProductKind.CARTRIDGE, "density_kg_m3": None,
     "cartridge_diameter_mm": 0, "cartridge_mass_kg": .5},
    {"kind": ExplosiveProductKind.CARTRIDGE, "density_kg_m3": None,
     "cartridge_diameter_mm": 40, "cartridge_mass_kg": 0},
])
def test_invalid_product_values_are_rejected(changes):
    with pytest.raises(ValueError): product(**changes)


def test_real_settings_dialog_catalogue_page_permissions_and_rows(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtWidgets import QApplication
    from ui import settings_dialog as module
    app = QApplication.instance() or QApplication([])
    adapter = MemoryCatalogue(); editable = ExplosiveCatalogue(adapter, adapter, can_edit=True)
    created = editable.create_product(product())
    editable.set_product_enabled(created.id, False)
    monkeypatch.setattr(module, "create_explosive_catalogue", lambda _context: editable)
    context = SimpleNamespace(current_user=SimpleNamespace(role="editor", can_edit=True, id=1),
                              session_factory=object())
    dialog = module.SettingsDialog(context)
    assert any(dialog.menu.item(i).text() == "Engineering catalogues" for i in range(dialog.menu.count()))
    assert dialog.catalogues_page.findChild(type(dialog.catalogues_page.empty_label)).text() != ""
    assert dialog.catalogues_page.add_button.isEnabled()
    assert dialog.catalogues_page.table.item(0, 0).text() == "Bulk"
    assert dialog.catalogues_page.table.item(0, 7).text() == "Disabled"
    dialog.close()
    viewer = ExplosiveCatalogue(adapter, adapter, can_edit=False)
    monkeypatch.setattr(module, "create_explosive_catalogue", lambda _context: viewer)
    context.current_user = SimpleNamespace(role="viewer", can_edit=False, id=2)
    dialog = module.SettingsDialog(context)
    assert not dialog.catalogues_page.add_button.isEnabled()
    assert not dialog.catalogues_page.edit_button.isEnabled()
    assert not dialog.catalogues_page.toggle_button.isEnabled()
    assert dialog.catalogues_page.table.rowCount() == 1
    dialog.close(); app.processEvents()


def test_product_dialog_required_numeric_fields_have_real_unset_state():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtWidgets import QApplication
    from ui.engineering_catalogues_page import ExplosiveProductDialog
    app = QApplication.instance() or QApplication([])
    dialog = ExplosiveProductDialog(); dialog.name_edit.setText("New product")

    assert dialog.density.text() == "Not set"
    with pytest.raises(ValueError, match="Density"):
        dialog.value()
    dialog.density.setValue(1000)
    assert dialog.value().density_kg_m3 == 1000

    dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData(ExplosiveProductKind.CARTRIDGE))
    assert dialog.diameter.text() == "Not set"
    assert dialog.mass.text() == "Not set"
    assert dialog.pitch.text() == "Not set"
    with pytest.raises(ValueError, match="Cartridge diameter"):
        dialog.value()
    dialog.diameter.setValue(40)
    with pytest.raises(ValueError, match="Cartridge mass"):
        dialog.value()
    dialog.diameter.setValue(dialog.diameter.minimum())
    dialog.mass.setValue(.5)
    with pytest.raises(ValueError, match="Cartridge diameter"):
        dialog.value()
    dialog.diameter.setValue(40)
    result = dialog.value()
    assert result.cartridge_diameter_mm == 40
    assert result.cartridge_mass_kg == .5
    assert result.default_pitch_m is None

    dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData(ExplosiveProductKind.BULK))
    assert dialog.density.value() == 1000
    dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData(ExplosiveProductKind.CARTRIDGE))
    assert dialog.pitch.text() == "Not set"
    dialog.close(); app.processEvents()


def test_white_product_uses_separate_color_cell_without_recoloring_name():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
    from ui.engineering_catalogues_page import EngineeringCataloguesPage
    app = QApplication.instance() or QApplication([])
    adapter = MemoryCatalogue(); service = ExplosiveCatalogue(adapter, adapter, can_edit=True)
    service.create_product(product(display_color="#FFFFFF"))
    page = EngineeringCataloguesPage(service, can_edit=True)
    name_item, color_item = page.table.item(0, 0), page.table.item(0, 2)
    assert name_item.foreground().style() == Qt.BrushStyle.NoBrush
    assert color_item.text() == "#FFFFFF"
    assert color_item.background().color() == QColor("#FFFFFF")
    page.close(); app.processEvents()
