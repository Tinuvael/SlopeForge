from __future__ import annotations

import os
import sys

import pytest

# The PostgreSQL job runs on a minimal Ubuntu image without libEGL. These are
# Qt interaction regressions and are covered by the Windows job; skip the module
# before importing PySide6 so pytest collection itself remains portable.
if sys.platform != "win32":
    pytest.skip("Qt drillhole UI regressions run in Windows CI", allow_module_level=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from domain.blasting.charge_design import (
    ChargeComponent,
    ChargeComponentKind,
    ExplosiveProductKind,
    ExplosiveProductSnapshot,
)
from domain.blasting.drillholes import Drillhole, DrillholePoint
from domain.blasting.technical_card import ActualDrillingGroup, BlastDrillingGroup
from ui.dialogs.drillhole_group_assignment_dialog import DrillholeSelectionView
from ui.pages.technical_card_widgets import (
    ENGINEERING_FIELD_DECIMALS,
    TechnicalCardEditorWidget,
    _fit_copied_charge_to_fact_depth,
)

_APP = None
_BULK = ExplosiveProductSnapshot(
    source_product_id=1,
    name="Emulsion",
    kind=ExplosiveProductKind.BULK,
    display_color="#336699",
    density_kg_m3=1200.0,
)


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _hole(hole_id: str, x: float, group_id: str | None = None) -> Drillhole:
    return Drillhole(
        hole_id,
        (
            DrillholePoint(x, 0.0, 630.0),
            DrillholePoint(x, 0.0, 620.0),
        ),
        engineering_group_id=group_id,
    )


def _design_with_charge() -> BlastDrillingGroup:
    return BlastDrillingGroup(
        name="Contour",
        average_depth_m=20.0,
        charge_components=[
            ChargeComponent("stem", ChargeComponentKind.STEMMING, 0.0, 5.0),
            ChargeComponent(
                "charge",
                ChargeComponentKind.BULK_EXPLOSIVE,
                5.0,
                20.0,
                _BULK,
            ),
        ],
    )


def test_copied_design_charge_is_fitted_instead_of_cleared_for_shallower_fact() -> None:
    design = _design_with_charge()
    actual = ActualDrillingGroup.from_design(design, "TC-R1")

    changed = _fit_copied_charge_to_fact_depth(actual, design, 19.0)

    assert changed is True
    assert len(actual.charge_components) == 2
    assert actual.charge_components[-1].start_depth_m == pytest.approx(5.0)
    assert actual.charge_components[-1].end_depth_m == pytest.approx(19.0)
    assert actual.copied_from_design is True
    assert actual.explosive_type == "Emulsion"


def test_auto_fitted_charge_can_follow_a_later_fact_depth_revision() -> None:
    design = _design_with_charge()
    actual = ActualDrillingGroup.from_design(design, "TC-R1")
    _fit_copied_charge_to_fact_depth(actual, design, 19.0)
    actual.average_depth_m = 19.0

    changed = _fit_copied_charge_to_fact_depth(actual, design, 18.0)

    assert changed is True
    assert actual.charge_components[-1].end_depth_m == pytest.approx(18.0)


def test_geometry_guard_cleared_charge_is_restored_on_next_group_refresh() -> None:
    design = _design_with_charge()
    actual = ActualDrillingGroup.from_design(design, "TC-R1")
    # Exact signature left by the earlier geometry guard implementation.
    actual.charge_components = []
    actual.stemming_length_m = 0.0
    actual.explosive_type = ""
    actual.copied_from_design = False

    TechnicalCardEditorWidget._restore_charge_cleared_by_geometry_guard(actual, design)

    assert len(actual.charge_components) == 2
    assert actual.charge_components[-1].end_depth_m == 20.0
    assert actual.copied_from_design is True


def test_manual_factual_charge_is_never_silently_refitted() -> None:
    design = _design_with_charge()
    actual = ActualDrillingGroup.from_design(design, "TC-R1")
    actual.charge_components = [
        ChargeComponent("manual-stem", ChargeComponentKind.STEMMING, 0.0, 4.0),
        ChargeComponent(
            "manual-charge",
            ChargeComponentKind.BULK_EXPLOSIVE,
            4.0,
            18.0,
            _BULK,
        ),
    ]

    changed = _fit_copied_charge_to_fact_depth(actual, design, 19.0)

    assert changed is False
    assert actual.charge_components[0].end_depth_m == 4.0
    assert actual.charge_components[1].start_depth_m == 4.0
    assert actual.charge_components[1].end_depth_m == 18.0


def test_assignment_view_starts_clean_and_excludes_holes_owned_by_other_groups() -> None:
    _app()
    holes = (
        _hole("CURRENT", 0.0, "DG-CURRENT"),
        _hole("OTHER", 10.0, "DG-OTHER"),
        _hole("FREE", 20.0, None),
    )
    view = DrillholeSelectionView(
        holes,
        selected_ids={"CURRENT"},
        target_group_id="DG-CURRENT",
    )

    assert view.selected_ids == set()
    assert view._available_hole_ids() == {"CURRENT", "FREE"}
    view.select_all()
    assert view.selected_ids == {"CURRENT", "FREE"}

    view._polygon_points = [(-5.0, -5.0), (25.0, -5.0), (25.0, 5.0), (-5.0, 5.0)]
    view.complete_polygon()
    assert "OTHER" not in view.selected_ids


def test_assignment_polygon_pen_is_cosmetic_and_thin() -> None:
    _app()
    view = DrillholeSelectionView((_hole("H1", 0.0), _hole("H2", 10.0)))
    view._polygon_points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    view._update_polygon_preview()

    assert view._polygon_preview is not None
    pen = view._polygon_preview.pen()
    assert pen.isCosmetic()
    assert pen.widthF() == 1.0


def test_mean_angular_deviation_uses_absolute_values() -> None:
    matches = [
        {"azimuth_deviation_deg": -2.0, "inclination_deviation_deg": 1.0},
        {"azimuth_deviation_deg": 4.0, "inclination_deviation_deg": -3.0},
    ]

    assert TechnicalCardEditorWidget._mean_absolute_deviation(
        matches, "azimuth_deviation_deg"
    ) == pytest.approx(3.0)
    assert TechnicalCardEditorWidget._mean_absolute_deviation(
        matches, "inclination_deviation_deg"
    ) == pytest.approx(2.0)


def test_requested_engineering_precision_is_explicit() -> None:
    assert ENGINEERING_FIELD_DECIMALS == {
        "hole_count": 0,
        "diameter_mm": 0,
        "subdrill_m": 1,
        "inclination_deg": 1,
        "azimuth_deg": 0,
        "spacing_m": 1,
        "line_offset_m": 1,
        "row_count": 0,
    }
