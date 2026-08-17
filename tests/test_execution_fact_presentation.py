"""Focused presentation regressions for the compact Execution fact workflow."""

import pytest

from domain.blasting.technical_card import new_technical_card
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
