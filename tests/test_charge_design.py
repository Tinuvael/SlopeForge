import math
from dataclasses import replace
import pytest

from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ChargeDesignValidationError, ChargeForm, ExplosiveClass,
    ExplosiveProduct, ExplosiveProductKind, available_air_intervals,
    cartridge_depths, validate_components,
)


def bulk(product_id=1):
    return ExplosiveProduct(product_id, "Bulk A", ExplosiveProductKind.BULK,
                            "#AA0000", density_kg_m3=1000)


def cartridge(product_id=2):
    return ExplosiveProduct(product_id, "Cartridge A", ExplosiveProductKind.CARTRIDGE,
                            "#00AA00", cartridge_diameter_mm=40,
                            cartridge_mass_kg=0.5, default_pitch_m=0.25)


def stemming(component_id, start, end):
    return ChargeComponent(component_id, ChargeComponentKind.STEMMING, start, end)


def test_snapshot_is_frozen_after_catalogue_product_changes():
    product = bulk(); snapshot = product.snapshot()
    product.name = "Bulk B"; product.density_kg_m3 = 1200; product.display_color = "#BB0000"
    assert (snapshot.name, snapshot.density_kg_m3, snapshot.display_color) == (
        "Bulk A", 1000, "#AA0000")


def test_snapshot_freezes_rich_catalogue_metadata():
    product=ExplosiveProduct(3,"Dynamite",ExplosiveProductKind.CARTRIDGE,"#112233",
        cartridge_diameter_mm=36,cartridge_mass_kg=.2,charge_form=ChargeForm.CARTRIDGED,
        explosive_class=ExplosiveClass.DYNAMITE,cartridge_length_mm=200)
    snapshot=product.snapshot(); product.cartridge_length_mm=250; product.explosive_class=ExplosiveClass.OTHER
    assert snapshot.explosive_class is ExplosiveClass.DYNAMITE and snapshot.cartridge_length_mm==200


def test_valid_component_properties_and_lengths():
    components = [
        stemming("s", 0, 1.5),
        ChargeComponent("b", ChargeComponentKind.BULK_EXPLOSIVE, 2, 5, bulk().snapshot()),
        ChargeComponent("c", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, 6, 8,
                        cartridge().snapshot(), 0.25),
    ]
    assert [item.length_m for item in components] == [1.5, 3, 2]
    assert components[1].product_snapshot.density_kg_m3 == 1000
    assert components[2].cartridge_pitch_m == 0.25


@pytest.mark.parametrize("start,end", [(-1, 1), (1, 1), (2, 1), (math.nan, 1),
                                        (0, math.inf)])
def test_invalid_component_depths_are_rejected(start, end):
    with pytest.raises(ChargeDesignValidationError): stemming("x", start, end)


def test_component_kind_specific_rules_are_enforced():
    b, c = bulk().snapshot(), cartridge().snapshot()
    invalid = [
        lambda: ChargeComponent("x", ChargeComponentKind.BULK_EXPLOSIVE, 0, 1, c),
        lambda: ChargeComponent("x", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, 0, 1, b, .2),
        lambda: ChargeComponent("x", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, 0, 1, c),
        lambda: ChargeComponent("x", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, 0, 1, c, 0),
        lambda: ChargeComponent("x", ChargeComponentKind.STEMMING, 0, 1, b),
        lambda: ChargeComponent("x", ChargeComponentKind.STEMMING, 0, 1, None, .2),
    ]
    for create in invalid:
        with pytest.raises(ChargeDesignValidationError): create()


def test_unsorted_component_validation_detects_overlap_and_bounds():
    valid = [stemming("c", 7, 8), stemming("a", 0, 2), stemming("b", 2, 4)]
    validate_components(valid, 10)
    with pytest.raises(ChargeDesignValidationError):
        validate_components([stemming("b", 2, 4), stemming("a", 0, 2.1)], 10)
    with pytest.raises(ChargeDesignValidationError):
        validate_components([stemming("x", 9, 10.1)], 10)


def test_touching_components_allow_only_machine_epsilon_not_real_overlap():
    exact = stemming("b", 1, 6)
    validate_components([stemming("a", 0, 1), exact], 6)
    noisy = stemming("noisy", 0, 1.0000000000000002)
    validate_components([noisy, exact], 6 - 1e-15)
    assert available_air_intervals(6, [noisy, exact]) == []
    with pytest.raises(ChargeDesignValidationError, match="overlap"):
        validate_components([stemming("overlap", 0, 1.001), exact], 6)


def test_air_intervals_are_exact_and_do_not_mutate_input_order():
    assert available_air_intervals(10, []) == [(0, 10)]
    items = [stemming("c", 8, 10), stemming("a", 0, 1), stemming("b", 3, 5)]
    assert available_air_intervals(10, items) == [(1, 3), (5, 8)]
    assert [item.id for item in items] == ["c", "a", "b"]
    assert available_air_intervals(10, [stemming("a", 0, 2), stemming("b", 2, 4)]) == [(4, 10)]


def test_cartridge_depths_are_inclusive_stable_and_kind_checked():
    deck = ChargeComponent("c", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, 2, 4,
                           cartridge().snapshot(), .5)
    assert cartridge_depths(deck) == (2.0, 2.5, 3.0, 3.5, 4.0)
    uneven = ChargeComponent("u", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, .1, 1.0,
                             cartridge().snapshot(), .3)
    assert cartridge_depths(uneven) == (.1, .4, .7, 1.0)
    assert cartridge_depths(replace(uneven, end_depth_m=.99)) == (.1, .4, .7)
    with pytest.raises(ChargeDesignValidationError):
        cartridge_depths(stemming("s", 0, 1))
