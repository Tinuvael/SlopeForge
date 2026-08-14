from math import pi
import pytest
from domain.blasting.charge_design import (ChargeComponent, ChargeComponentKind,
    ExplosiveProduct, ExplosiveProductKind, component_explosive_mass_kg)
from domain.blasting.charge_presets import (ChargeDesignPreset, ChargePresetComponent,
    instantiate_preset)
from domain.blasting.technical_card import BlastEventTechnicalCard

def bulk(density=1000, enabled=True):
    return ExplosiveProduct(1,"Bulk A",ExplosiveProductKind.BULK,"#112233",enabled=enabled,density_kg_m3=density)

def test_bulk_and_cartridge_engineering_mass():
    component=ChargeComponent("a",ChargeComponentKind.BULK_EXPLOSIVE,2,7,bulk().snapshot())
    assert component_explosive_mass_kg(component,100)==pytest.approx(pi*.1**2/4*5*1000)
    assert component_explosive_mass_kg(component,None) is None
    cartridge=ExplosiveProduct(2,"Cart",ExplosiveProductKind.CARTRIDGE,"#445566",
        cartridge_diameter_mm=32,cartridge_mass_kg=.5).snapshot()
    deck=ChargeComponent("b",ChargeComponentKind.CARTRIDGE_EXPLOSIVE,0,1,cartridge,.25)
    assert component_explosive_mass_kg(deck,100)==2.5

def test_canonical_component_roundtrip_has_frozen_snapshot_and_no_legacy_duplicates():
    raw={"id":"TC","blast_event_id":"E","active_revision_id":"R","revisions":[{
        "id":"R","technical_card_id":"TC","revision_number":1,"created_at":"2026-01-01T00:00:00",
        "geometry_revision_id":"G","event_type":"contour","status":"draft","common_parameters":{},
        "drilling_groups":[{"id":"DG","average_depth_m":10,"hole_count":2,"diameter_mm":100,
          "charge_components":[{"id":"C","kind":"bulk_explosive","start_depth_m":1,"end_depth_m":9,
          "product_snapshot":{"source_product_id":1,"name":"Bulk A","kind":"bulk","display_color":"#112233","density_kg_m3":1000},"cartridge_pitch_m":None}]}],
        "contour_parameters":{},"actual_execution":{}}]}
    card=BlastEventTechnicalCard.from_dict(raw); component=card.active_revision().drilling_groups[0].charge_components[0]
    assert component.product_snapshot.density_kg_m3==1000
    encoded=card.to_dict()["revisions"][0]["drilling_groups"][0]
    assert "charge_components" in encoded and "total_charge_mass_kg" not in encoded
    assert "stemming_length_m" not in encoded and "planned_drilling_length_m" not in encoded

def test_preset_uses_current_product_snapshot_and_rejects_invalid_application():
    preset=ChargeDesignPreset(1,7,"Standard",[ChargePresetComponent(
        ChargeComponentKind.BULK_EXPLOSIVE,0,10,1)])
    r1=instantiate_preset(preset,[bulk(1000)],10)
    r2=instantiate_preset(preset,[bulk(1200)],12)
    assert r1[0].product_snapshot.density_kg_m3==1000
    assert r2[0].product_snapshot.density_kg_m3==1200 and r1[0].id != r2[0].id
    with pytest.raises(ValueError): instantiate_preset(preset,[bulk(1200)],8)
    with pytest.raises(ValueError): instantiate_preset(preset,[bulk(1200,False)],12)
