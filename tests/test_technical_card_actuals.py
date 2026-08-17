"""Design/fact separation and backwards-compatibility regression tests."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from domain.blasting.technical_card import (
    ActualDrillingGroup, ActualExecution, BlastDrillingGroup,
    BlastEventTechnicalCard, comparison_value, charge_engineering_content,
)
from domain.blasting.charge_design import ChargeComponent, ChargeComponentKind, ExplosiveProduct, ExplosiveProductKind
from tests.test_technical_cards import event
from domain.blasting.technical_card import new_technical_card


def designs():
    return [
        BlastDrillingGroup(id="DG-1", name="Сеть", hole_count=10, average_depth_m=12,
            burden_m=4, spacing_m=5, charge_mass_per_hole_kg=20),
        BlastDrillingGroup(id="DG-2", group_type="buffer", name="Буфер", hole_count=2,
            average_depth_m=8, total_charge_mass_kg=30),
    ]


def test_lns_and_spacing_keep_existing_domain_fields_and_design_override():
    group = BlastDrillingGroup(hole_count=3, average_depth_m=10, burden_m=4, spacing_m=5)
    assert group.burden_m == 4 and group.spacing_m == 5
    assert not hasattr(group, "lns_m") and group.drilling_length() == 30
    group.legacy_actual_drilling_length_m = 99
    assert group.drilling_length() == 30
    group.planned_drilling_length_m = 31  # legacy payload field no longer overrides canonical design
    assert group.drilling_length() == 30


def test_copy_all_is_independent_and_links_stable_ids():
    source = designs(); execution = ActualExecution()
    execution.copy_from_design(source, "TC-R1", "replace")
    assert [g.design_group_id for g in execution.actual_drilling_groups] == ["DG-1", "DG-2"]
    assert all(g.copied_from_design and g.copied_at for g in execution.actual_drilling_groups)
    source[0].hole_count = 100
    assert execution.actual_drilling_groups[0].hole_count == 10
    assert execution.actual_drilling_groups[0].charge_decks is not source[0].charge_decks


def test_copy_modes_are_safe_and_one_group_is_isolated():
    source = designs(); execution = ActualExecution(); execution.copy_from_design(source, "R1", "replace")
    execution.actual_drilling_groups[0].hole_count = 7
    source[0].hole_count = 12; source[0].spacing_m = 6
    execution.copy_from_design(source, "R2", "fill_empty")
    assert execution.actual_drilling_groups[0].hole_count == 7
    execution.actual_drilling_groups.pop()
    execution.copy_from_design(source, "R2", "add_missing")
    assert len(execution.actual_drilling_groups) == 2 and execution.actual_drilling_groups[0].hole_count == 7
    before = execution.actual_drilling_groups[1].hole_count
    execution.copy_one(source[0], execution.actual_drilling_groups[0], "R2", "replace")
    assert execution.actual_drilling_groups[0].hole_count == 12
    assert execution.actual_drilling_groups[1].hole_count == before
    execution.copy_from_design(source, "R3", "replace")
    assert [g.hole_count for g in execution.actual_drilling_groups] == [12, 2]


def test_unplanned_group_and_actual_calculations():
    execution = ActualExecution(actual_block_volume_m3=1000, actual_drilling_groups=[
        ActualDrillingGroup(design_group_id=None, hole_count=10, average_depth_m=12,
            charge_mass_per_hole_kg=20, rejected_hole_count=1, wet_hole_count=2),
        ActualDrillingGroup(hole_count=2, average_depth_m=8, drilling_length_m=20,
            total_charge_mass_kg=30, redrilled_hole_count=1, uncharged_hole_count=1),
    ])
    execution.recalculate()
    assert execution.actual_drilling_groups[0].design_group_id is None
    assert execution.actual_total_hole_count == 12
    assert execution.actual_total_drilling_length_m == 140
    assert execution.actual_total_explosive_mass_kg == 230
    assert execution.actual_average_depth_m == pytest.approx(136 / 12)
    assert execution.actual_rock_yield_m3_per_drilling_m == pytest.approx(1000 / 140)
    assert execution.actual_specific_drilling_m_per_m3 == pytest.approx(140 / 1000)
    assert execution.actual_powder_factor_kg_per_m3 == pytest.approx(230 / 1000)
    assert (execution.rejected_hole_count, execution.redrilled_hole_count,
            execution.wet_hole_count, execution.uncharged_hole_count) == (1, 1, 2, 1)


def test_zero_denominators_and_comparison_are_safe():
    execution = ActualExecution(actual_block_volume_m3=0,
        actual_drilling_groups=[ActualDrillingGroup(hole_count=1, average_depth_m=0, charge_mass_per_hole_kg=2)])
    execution.recalculate()
    assert execution.actual_rock_yield_m3_per_drilling_m is None
    assert execution.actual_specific_drilling_m_per_m3 is None
    assert execution.actual_powder_factor_kg_per_m3 is None
    row = comparison_value("Сеть", "Скважины", "шт", 10, 12)
    assert row["absolute_deviation"] == 2 and row["relative_deviation_percent"] == 20
    assert comparison_value("Сеть", "Скважины", "шт", 0, 2)["relative_deviation_percent"] is None


@pytest.mark.parametrize("kind", ["production", "contour"])
def test_actual_groups_round_trip_for_both_event_types(kind):
    card, draft = new_technical_card(event(kind)); draft.actual_execution.copy_from_design(draft.drilling_groups, "draft", "replace")
    card.save_revision(draft)
    restored = BlastEventTechnicalCard.from_dict(json.loads(json.dumps(card.to_dict())))
    actual = restored.active_revision().actual_execution.actual_drilling_groups[0]
    assert actual.design_group_id == draft.drilling_groups[0].id


def test_old_json_summary_and_legacy_group_length_migrate_without_design_mixing():
    card, draft = new_technical_card(event()); saved = card.save_revision(draft)
    raw = card.to_dict(); group = raw["revisions"][0]["drilling_groups"][0]
    group["hole_count"] = 2; group["average_depth_m"] = 10; group["actual_drilling_length_m"] = 27
    raw["revisions"][0]["actual_execution"] = {"actual_hole_count": 2, "actual_drilling_length_m": 27}
    restored = BlastEventTechnicalCard.from_dict(raw); revision = restored.active_revision()
    assert revision.drilling_groups[0].drilling_length() == 20
    assert revision.actual_execution.actual_drilling_groups[0].drilling_length_m == 27
    assert revision.actual_execution.migration_warnings
    future = restored.to_dict()["revisions"][0]["drilling_groups"][0]
    assert "actual_drilling_length_m" not in future and "legacy_actual_drilling_length_m" not in future


def test_second_revision_never_mutates_first_actual_snapshot():
    card, draft = new_technical_card(event()); draft.actual_execution.copy_from_design(draft.drilling_groups, None, "replace")
    first = card.save_revision(draft); edit = deepcopy(first); edit.actual_execution.actual_drilling_groups[0].hole_count = 99
    second = card.save_revision(edit)
    assert first.actual_execution.actual_drilling_groups[0].hole_count != second.actual_execution.actual_drilling_groups[0].hole_count


def test_actual_charge_is_a_deep_snapshot_and_uses_design_calculations():
    product=ExplosiveProduct(7,"ANFO",ExplosiveProductKind.BULK,"#C87533",density_kg_m3=1000)
    component=ChargeComponent("design-id",ChargeComponentKind.BULK_EXPLOSIVE,1,3,product.snapshot())
    design=BlastDrillingGroup(id="DG",hole_count=4,diameter_mm=100,average_depth_m=5,charge_components=[component])
    actual=ActualDrillingGroup.from_design(design)
    assert actual.charge_components == design.charge_components
    assert actual.charge_components is not design.charge_components
    assert actual.effective_charge_mass() == pytest.approx(design.total_explosive_mass())
    actual.charge_components[0]=replace(actual.charge_components[0],end_depth_m=4)
    assert design.charge_components[0].end_depth_m == 3
    assert not actual.charge_matches(design)


def test_charge_comparison_ignores_component_ids_but_not_engineering_content():
    product=ExplosiveProduct(8,"Emulsion",ExplosiveProductKind.BULK,"#112233",density_kg_m3=1100)
    left=ChargeComponent("left",ChargeComponentKind.BULK_EXPLOSIVE,1,2,product.snapshot())
    right=ChargeComponent("right",ChargeComponentKind.BULK_EXPLOSIVE,1,2,product.snapshot())
    assert charge_engineering_content([left]) == charge_engineering_content([right])
    right=replace(right,end_depth_m=2.5)
    assert charge_engineering_content([left]) != charge_engineering_content([right])
