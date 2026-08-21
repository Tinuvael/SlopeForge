"""Focused presentation regressions for the compact Execution fact workflow."""

import pytest

from domain.blasting.charge_design import ChargeComponent, ChargeComponentKind
from domain.blasting.technical_card import BlastDrillingGroup, new_technical_card
from tests.test_technical_cards import event


def test_execution_fact_uses_columnar_plan_delta_and_vertical_exceptions():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from app.localization import tr
    from ui.editors.technical_card_editor import TechnicalCardDialog

    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event()
    card, draft = new_technical_card(blast)
    design = draft.drilling_groups[0]
    design.hole_count = 13
    design.diameter_mm = 145
    design.average_depth_m = 9
    design.subdrill_m = 0.2
    design.burden_m = 4
    design.spacing_m = 5
    design.row_count = 5
    draft.actual_execution.copy_from_design(draft.drilling_groups, None, "replace")
    draft.actual_execution.actual_drilling_groups[0].hole_count = 20

    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)
    group = dialog.actual_cards_layout.itemAt(0).widget()
    drilling = group.findChild(widgets.QGroupBox, "actualDrillingArea")
    grid = drilling.layout()

    assert isinstance(grid, widgets.QGridLayout)
    assert [grid.itemAtPosition(0, column).widget().text() for column in range(4)] == [
        tr("Parameter"), tr("Actual"), tr("Plan"), "Δ"
    ]
    hole_count = drilling.findChild(widgets.QDoubleSpinBox, "hole_count")
    assert hole_count.decimals() == 0
    assert drilling.findChild(widgets.QLabel, "actualPlan_hole_count").text() == "13"
    delta = drilling.findChild(widgets.QLabel, "actualDelta_hole_count")
    assert delta.text() == "+7"
    hole_count.setValue(13)
    app.processEvents()
    assert delta.text() == "—"

    exceptions = next(box for box in group.findChildren(widgets.QGroupBox)
                      if box.title() == tr("Execution exceptions"))
    exception_grid = exceptions.layout()
    assert [exception_grid.itemAtPosition(row, 0).widget().text() for row in range(4)] == [
        tr("Rejected"), tr("Redrilled"), tr("Wet"), tr("Uncharged")
    ]
    assert all(exception_grid.itemAtPosition(row, 1).widget() is not None for row in range(4))

    charge_comparison = group.findChild(widgets.QWidget, "actualChargeComparison")
    assert charge_comparison is not None


def test_charge_comparison_uses_compact_one_decimal_values_and_quiet_zero_delta():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog

    app = widgets.QApplication.instance() or widgets.QApplication([])
    row = {key: widgets.QLabel() for key in ("plan", "actual", "delta")}

    TechnicalCardDialog._set_charge_comparison_row(row, 118.894, 148.6174)
    assert row["plan"].text() == "118.9"
    assert row["actual"].text() == "148.6"
    assert row["delta"].text() == "+29.7"

    TechnicalCardDialog._set_charge_comparison_row(row, 42.0, 42.0)
    assert row["plan"].text() == "42"
    assert row["actual"].text() == "42"
    assert row["delta"].text() == "—"


def test_existing_execution_grid_uses_circular_azimuth_delta_and_contains_ratios():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog

    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    design = draft.drilling_groups[0]; design.azimuth_deg = 359; design.burden_m = 4; design.spacing_m = 5
    draft.actual_execution.copy_from_design(draft.drilling_groups, None, "replace")
    actual = draft.actual_execution.actual_drilling_groups[0]; actual.azimuth_deg = 1
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)
    group = dialog.actual_cards_layout.itemAt(0).widget()
    assert group.findChild(widgets.QLabel, "actualDelta_azimuth_deg").text() == "+2"
    actual_azimuth = group.findChild(widgets.QDoubleSpinBox, "azimuth_deg")
    actual_azimuth.setValue(359); design.azimuth_deg = 1
    plan = group.findChild(widgets.QLabel, "actualPlan_azimuth_deg")
    delta = group.findChild(widgets.QLabel, "actualDelta_azimuth_deg")
    TechnicalCardDialog._set_comparison_labels(plan, delta, 1, 359, circular=True)
    assert delta.text() == "-2"
    assert group.findChild(widgets.QLabel, "engineeringRatios") is not None


def test_design_group_renderer_does_not_duplicate_design_actual_table():
    source = __import__("pathlib").Path("ui/editors/technical_card_editor.py").read_text()
    design_renderer = source.split("def _render_groups(self):", 1)[1].split("def _add_number", 1)[0]
    assert "design_group_id" not in design_renderer
    assert "designActualSummary" not in design_renderer


def test_two_actual_group_callbacks_refresh_only_their_own_derived_widgets():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    from ui.widgets.borehole_charge_builder import BoreholeChargeBuilder

    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    first = draft.drilling_groups[0]; first.average_depth_m = 10; first.burden_m = 4; first.spacing_m = 5
    second = BlastDrillingGroup(name="Second", average_depth_m=10, burden_m=8, spacing_m=4)
    draft.drilling_groups.append(second)
    draft.actual_execution.copy_from_design(draft.drilling_groups, None, "replace")
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)
    cards = [dialog.actual_cards_layout.itemAt(index).widget() for index in range(2)]
    first_ratios = cards[0].findChild(widgets.QLabel, "engineeringRatios")
    second_ratios = cards[1].findChild(widgets.QLabel, "engineeringRatios")
    second_ratio_text = second_ratios.text()
    second_stemming = cards[1].findChild(widgets.QLabel, "actualDerived_stemming_actual")
    second_stemming_text = second_stemming.text()

    cards[0].findChild(widgets.QDoubleSpinBox, "burden_m").setValue(2)
    cards[0].findChild(widgets.QDoubleSpinBox, "mean_toe_deviation_m").setValue(1)
    component = ChargeComponent("S-1", ChargeComponentKind.STEMMING, 0, 3)
    cards[0].findChild(BoreholeChargeBuilder).components_changed.emit([component])
    app.processEvents()

    assert "B/S: 0.4" in first_ratios.text()
    assert "mean toe deviation / burden: 0.5" in first_ratios.text()
    assert cards[0].findChild(widgets.QLabel, "actualDerived_stemming_actual").text() == "3"
    assert second_ratios.text() == second_ratio_text
    assert second_stemming.text() == second_stemming_text
