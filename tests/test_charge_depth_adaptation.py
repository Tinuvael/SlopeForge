import pytest

from domain.blasting.charge_design import (
    ChargeComponent,
    ChargeComponentKind,
    ExplosiveProductKind,
    ExplosiveProductSnapshot,
    available_air_intervals,
    fit_charge_components_to_hole_depth,
    validate_components,
)


_BULK = ExplosiveProductSnapshot(
    source_product_id=1,
    name="Emulsion",
    kind=ExplosiveProductKind.BULK,
    display_color="#336699",
    density_kg_m3=1200.0,
)


def _stem(component_id: str, start: float, end: float) -> ChargeComponent:
    return ChargeComponent(component_id, ChargeComponentKind.STEMMING, start, end)


def _bulk(component_id: str, start: float, end: float) -> ChargeComponent:
    return ChargeComponent(
        component_id,
        ChargeComponentKind.BULK_EXPLOSIVE,
        start,
        end,
        _BULK,
    )


def test_longer_factual_hole_keeps_design_charge_and_adds_toe_air() -> None:
    design = [_stem("stem", 0.0, 5.0), _bulk("charge", 5.0, 20.0)]

    fitted = fit_charge_components_to_hole_depth(design, 22.0)

    assert fitted == design
    assert available_air_intervals(22.0, fitted) == [(20.0, 22.0)]


def test_existing_toe_air_is_consumed_before_any_charge_change() -> None:
    design = [_stem("stem", 0.0, 5.0), _bulk("charge", 5.0, 18.0)]

    fitted = fit_charge_components_to_hole_depth(design, 19.0)

    assert fitted == design
    assert available_air_intervals(19.0, fitted) == [(18.0, 19.0)]


def test_shallower_factual_hole_shifts_lower_charge_up_into_existing_air() -> None:
    design = [_stem("stem", 0.0, 5.0), _bulk("charge", 7.0, 20.0)]

    fitted = fit_charge_components_to_hole_depth(design, 19.0)

    assert fitted[0] == design[0]
    assert fitted[1].start_depth_m == pytest.approx(6.0)
    assert fitted[1].end_depth_m == pytest.approx(19.0)
    assert fitted[1].length_m == pytest.approx(design[1].length_m)
    assert available_air_intervals(19.0, fitted) == [(5.0, 6.0)]


def test_shallower_factual_hole_shortens_toe_charge_when_no_air_is_available() -> None:
    design = [_stem("stem", 0.0, 5.0), _bulk("charge", 5.0, 20.0)]

    fitted = fit_charge_components_to_hole_depth(design, 19.0)

    assert fitted[0] == design[0]
    assert fitted[1].start_depth_m == pytest.approx(5.0)
    assert fitted[1].end_depth_m == pytest.approx(19.0)
    assert fitted[1].length_m == pytest.approx(14.0)
    validate_components(fitted, 19.0)


def test_air_is_used_first_then_only_remaining_shortage_trims_toe_charge() -> None:
    design = [_stem("stem", 0.0, 5.0), _bulk("charge", 7.0, 20.0)]

    fitted = fit_charge_components_to_hole_depth(design, 17.0)

    # Two metres of the three-metre shortage are absorbed by the 5-7 m air
    # interval. The final one metre is removed from the toe-most charge.
    assert fitted[1].start_depth_m == pytest.approx(5.0)
    assert fitted[1].end_depth_m == pytest.approx(17.0)
    assert fitted[1].length_m == pytest.approx(12.0)
    validate_components(fitted, 17.0)


def test_fitting_never_mutates_the_design_components() -> None:
    design = [_stem("stem", 0.0, 5.0), _bulk("charge", 7.0, 20.0)]

    fit_charge_components_to_hole_depth(design, 17.0)

    assert design[0].start_depth_m == 0.0
    assert design[0].end_depth_m == 5.0
    assert design[1].start_depth_m == 7.0
    assert design[1].end_depth_m == 20.0
