from copy import deepcopy
import json
import math

import pytest

from application.use_cases.charge_presets import ChargePresets
from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ChargeDesignPreset, ChargeForm,
    ChargePresetComponent, ExplosiveProduct, ExplosiveProductKind,
)
from domain.blasting.technical_card import BlastEventTechnicalCard, DesignSlopeOrientation
from tests.test_technical_cards import event
from domain.blasting.technical_card import new_technical_card


def bulk(product_id=1, density=900):
    return ExplosiveProduct(product_id,"Igdanite",ExplosiveProductKind.BULK,"#C87533",
        density_kg_m3=density,charge_form=ChargeForm.BULK)


def cartridge(product_id=2):
    return ExplosiveProduct(product_id,"Cartridge",ExplosiveProductKind.CARTRIDGE,"#49A35B",
        cartridge_diameter_mm=32,cartridge_mass_kg=0.5,default_pitch_m=0.5,
        charge_form=ChargeForm.CARTRIDGED)


def test_charge_components_snapshot_roundtrip_and_engineering_totals():
    blast=event(); card,draft=new_technical_card(blast); group=draft.drilling_groups[0]
    group.hole_count=2; group.diameter_mm=146; group.average_depth_m=36; group.subdrill_m=1
    group.charge_components=[ChargeComponent("bulk",ChargeComponentKind.BULK_EXPLOSIVE,5,7,bulk().snapshot())]
    saved=card.save_revision(draft); restored=BlastEventTechnicalCard.from_dict(json.loads(json.dumps(card.to_dict())))
    loaded=restored.active_revision().drilling_groups[0]
    assert isinstance(loaded.charge_components[0],ChargeComponent)
    assert loaded.charge_components[0].product_snapshot.density_kg_m3==900
    assert loaded.drilling_length()==72
    expected=math.pi*(0.146**2)/4*2*900
    assert loaded.explosive_mass_per_hole_kg()==pytest.approx(expected)
    assert loaded.total_explosive_mass()==pytest.approx(expected*2)
    assert saved.production_parameters.total_explosive_mass_kg==pytest.approx(expected*2)
    payload=card.to_dict()["revisions"][0]["drilling_groups"][0]
    assert "charge_components" in payload
    for legacy in ("charge_decks","explosive_type","charge_mass_per_hole_kg","total_charge_mass_kg",
                   "stemming_length_m","planned_drilling_length_m"):
        assert legacy not in payload


def test_cartridge_count_mass_and_design_to_actual_compatibility():
    blast=event(); card,draft=new_technical_card(blast); group=draft.drilling_groups[0]
    group.hole_count=3; group.diameter_mm=146; group.average_depth_m=10
    group.charge_components=[ChargeComponent("cart",ChargeComponentKind.CARTRIDGE_EXPLOSIVE,1,2,
        cartridge().snapshot(),0.5),ChargeComponent("stem",ChargeComponentKind.STEMMING,0,1)]
    assert group.explosive_mass_per_hole_kg()==1.5
    actual=draft.actual_execution.copy_one(group)
    assert actual.drilling_length_m==30 and actual.charge_mass_per_hole_kg==1.5
    assert actual.total_charge_mass_kg==4.5 and actual.stemming_length_m==1


class MemoryPersistence:
    def __init__(self): self.values=[]; self.next_id=1
    def list_presets(self,site_id): return [x for x in self.values if x.site_id==site_id]
    def create_preset(self,site_id,name,components):
        value=ChargeDesignPreset(self.next_id,site_id,name,components); self.next_id+=1; self.values.append(value); return value
    def update_preset(self,preset_id,site_id,name,components):
        value=ChargeDesignPreset(preset_id,site_id,name,components); self.values=[value if x.id==preset_id else x for x in self.values]; return value
    def delete_preset(self,preset_id,site_id): self.values=[x for x in self.values if x.id!=preset_id]


def test_project_preset_uses_current_catalogue_snapshot_and_rejects_short_hole():
    persistence=MemoryPersistence(); service=ChargePresets(persistence,site_id=7,can_edit=True)
    original=ChargeComponent("old",ChargeComponentKind.BULK_EXPLOSIVE,0,10,bulk(density=800).snapshot())
    preset=service.create("Standard",[original],[bulk(density=800)])
    current=bulk(density=950)
    applied=service.apply(preset,[current],12)
    assert applied[0].id!="old" and applied[0].product_snapshot.density_kg_m3==950
    with pytest.raises(ValueError,match="beyond"):
        service.apply(preset,[current],8)
    assert ChargePresets(persistence,site_id=8,can_edit=True).list_presets()==[]


def test_preset_name_and_catalogue_are_validated_before_adapter_call():
    class RejectPersistence(MemoryPersistence):
        called=False
        def create_preset(self,*args): self.called=True; return super().create_preset(*args)
    persistence=RejectPersistence(); service=ChargePresets(persistence,site_id=7,can_edit=True)
    with pytest.raises(ValueError,match="255"):
        service.create("x"*256,[],[])
    assert persistence.called is False
    stale=ChargeComponent("old",ChargeComponentKind.BULK_EXPLOSIVE,0,1,bulk(99).snapshot())
    with pytest.raises(ValueError,match="current enabled"):
        service.create("Stale",[stale],[bulk(1)])
    assert persistence.called is False


def test_design_slope_roundtrip_history_and_old_payload():
    blast=event(); card,draft=new_technical_card(blast)
    draft.design_slope_orientation=DesignSlopeOrientation(130,65); first=card.save_revision(draft)
    edit=deepcopy(first); edit.design_slope_orientation=DesignSlopeOrientation(140,70); card.save_revision(edit)
    restored=BlastEventTechnicalCard.from_dict(json.loads(json.dumps(card.to_dict())))
    assert (restored.revisions[0].design_slope_orientation.azimuth_deg,restored.revisions[0].design_slope_orientation.angle_deg)==(130,65)
    payload=card.to_dict(); payload["revisions"][0].pop("design_slope_orientation")
    assert BlastEventTechnicalCard.from_dict(payload).revisions[0].design_slope_orientation.azimuth_deg is None


def test_compact_builder_ui_and_no_legacy_design_controls(monkeypatch):
    widgets=pytest.importorskip("PySide6.QtWidgets",exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    from ui.widgets.borehole_charge_builder import BoreholeChargeBuilder
    app=widgets.QApplication.instance() or widgets.QApplication([])
    blast=event(); card,draft=new_technical_card(blast)
    service=ChargePresets(MemoryPersistence(),site_id=1,can_edit=True)
    dialog=TechnicalCardDialog(blast,card,draft,lambda *_:None,explosive_products=[bulk()],charge_presets=service)
    group=dialog.group_cards_layout.itemAt(0).widget()
    assert group.property("engineeringComposition")=="left-right"
    assert group.findChild(widgets.QDoubleSpinBox,"average_depth_m").maximumWidth()==160
    assert group.findChild(BoreholeChargeBuilder,"boreholeChargeBuilder") is None
    group.findChild(widgets.QDoubleSpinBox,"average_depth_m").setValue(10); app.processEvents()
    assert group.findChild(BoreholeChargeBuilder,"boreholeChargeBuilder") is not None
    assert group.findChild(widgets.QComboBox,"chargePresetCombo") is not None
    assert group.findChild(widgets.QDoubleSpinBox,"inclination_deg") is not None
    assert group.findChild(widgets.QDoubleSpinBox,"azimuth_deg") is not None
    for legacy in ("charge_mass_per_hole_kg","charge_concentration_kg_per_m","total_charge_mass_kg",
                   "stemming_length_m","air_deck_count","planned_drilling_length_m"):
        assert group.findChild(widgets.QDoubleSpinBox,legacy) is None
    dialog.design_slope_azimuth.setValue(360); dialog._save("draft")
    assert draft.design_slope_orientation.azimuth_deg==0


def test_preset_load_cancel_preserves_components_and_replace_applies(monkeypatch):
    widgets=pytest.importorskip("PySide6.QtWidgets",exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app=widgets.QApplication.instance() or widgets.QApplication([])
    blast=event(); card,draft=new_technical_card(blast); group=draft.drilling_groups[0]
    group.average_depth_m=3; group.diameter_mm=100
    original=ChargeComponent("old",ChargeComponentKind.BULK_EXPLOSIVE,1,2,bulk().snapshot()); group.charge_components=[original]
    service=ChargePresets(MemoryPersistence(),site_id=1,can_edit=True)
    service.create("Stemming",[ChargeComponent("s",ChargeComponentKind.STEMMING,0,1)],[])
    dialog=TechnicalCardDialog(blast,card,draft,lambda *_:None,explosive_products=[bulk()],charge_presets=service)
    combo=dialog.findChild(widgets.QComboBox,"chargePresetCombo"); state={"builder":None}; refreshed=[]
    monkeypatch.setattr(widgets.QMessageBox,"exec",lambda self:self.button(widgets.QMessageBox.StandardButton.Cancel).click())
    dialog._load_preset(combo,group,state,lambda:refreshed.append(True)); assert group.charge_components==[original]
    def accept(message):
        next(button for button in message.buttons() if message.buttonRole(button)==widgets.QMessageBox.ButtonRole.AcceptRole).click()
    monkeypatch.setattr(widgets.QMessageBox,"exec",accept)
    dialog._load_preset(combo,group,state,lambda:refreshed.append(True))
    assert group.charge_components[0].kind is ChargeComponentKind.STEMMING and refreshed


def test_duplicate_preset_error_is_presented_without_escaping_qt_slot(monkeypatch):
    widgets=pytest.importorskip("PySide6.QtWidgets",exc_type=ImportError)
    from application.errors import CatalogueConflictError
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app=widgets.QApplication.instance() or widgets.QApplication([])
    blast=event(); card,draft=new_technical_card(blast)
    class DuplicateService:
        def list_presets(self):return []
        def create(self,*_):raise CatalogueConflictError("A charge preset with this name already exists")
    dialog=TechnicalCardDialog(blast,card,draft,lambda *_:None,explosive_products=[],charge_presets=DuplicateService())
    messages=[]; monkeypatch.setattr(widgets.QInputDialog,"getText",lambda *_:("Duplicate",True))
    monkeypatch.setattr(widgets.QMessageBox,"warning",lambda *args:messages.append(args[-1]))
    dialog._save_preset(None,draft.drilling_groups[0])
    assert messages==["A charge preset with this name already exists"]
