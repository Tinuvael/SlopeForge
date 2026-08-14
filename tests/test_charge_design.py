import math
import pytest

from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ChargeDesignValidationError,
    ExplosiveProduct, ExplosiveProductKind, available_air_intervals,
    validate_components,
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


def test_air_intervals_are_exact_and_do_not_mutate_input_order():
    assert available_air_intervals(10, []) == [(0, 10)]
    items = [stemming("c", 8, 10), stemming("a", 0, 1), stemming("b", 3, 5)]
    assert available_air_intervals(10, items) == [(1, 3), (5, 8)]
    assert [item.id for item in items] == ["c", "a", "b"]
    assert available_air_intervals(10, [stemming("a", 0, 2), stemming("b", 2, 4)]) == [(4, 10)]
