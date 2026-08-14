from dataclasses import replace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ExplosiveProduct, ExplosiveProductKind,
    validate_components,
)
from ui.widgets.borehole_charge_builder import (
    BoreholeChargeBuilder, depth_to_scene_y, scene_y_to_depth, snap_depth,
)


def app(): return QApplication.instance() or QApplication([])


def bulk():
    return ExplosiveProduct(1, "Bulk A", ExplosiveProductKind.BULK, "#C87533",
                            density_kg_m3=1000)


def cartridge():
    return ExplosiveProduct(2, "Cartridge A", ExplosiveProductKind.CARTRIDGE, "#49A35B",
                            cartridge_diameter_mm=40, cartridge_mass_kg=.5,
                            default_pitch_m=.5)


def test_conversion_and_snap_helpers_are_stable():
    assert snap_depth(2.04) == 2.0 and snap_depth(2.06) == 2.1
    for depth in (0, 2.5, 10):
        assert scene_y_to_depth(depth_to_scene_y(depth, 10, 28, 400), 10, 28, 400) == pytest.approx(depth)


def test_empty_hole_add_and_delete_stemming():
    app(); widget = BoreholeChargeBuilder(10, None, [], [])
    assert widget.components() == [] and widget.air_intervals() == [(0.0, 10.0)]
    assert widget.findChild(type(widget.add_button), "addComponentButton").text() == "Add component"
    widget.select_air((0.0, 10.0)); assert widget.add_stemming()
    component = widget.components()[0]
    assert (component.start_depth_m, component.end_depth_m, component.kind) == (0, .1, ChargeComponentKind.STEMMING)
    assert widget.delete_selected_component() and widget.air_intervals() == [(0.0, 10.0)]


def test_products_are_snapshotted_and_cartridge_pitch_updates_count():
    app(); b, c = bulk(), cartridge(); widget = BoreholeChargeBuilder(10, 100, [b, c], [])
    assert widget.add_component(ChargeComponentKind.BULK_EXPLOSIVE, b)
    frozen = widget.components()[0].product_snapshot
    b.name = "Changed"; b.display_color = "#000000"
    assert widget.components()[0].product_snapshot == frozen
    assert widget.add_component(ChargeComponentKind.CARTRIDGE_EXPLOSIVE, c)
    deck = widget.components()[1]
    widget._replace_selected(replace(deck, start_depth_m=2, end_depth_m=4))
    assert widget.count_label.text() == "5"
    widget.pitch_spin.setValue(1); widget._pitch_edit()
    assert widget.count_label.text() == "3" and widget.components()[1].cartridge_pitch_m == 1


def test_numeric_sync_overlap_and_hole_depth_rejection():
    app(); a = ChargeComponent("a", ChargeComponentKind.STEMMING, 0, 2)
    b = ChargeComponent("b", ChargeComponentKind.STEMMING, 3, 5)
    widget = BoreholeChargeBuilder(10, None, [], [a, b]); widget.select_component("b")
    widget.start_spin.setValue(2.5); widget._numeric_edit("start")
    widget.end_spin.setValue(5.0); widget._numeric_edit("end")
    widget.length_spin.setValue(1); widget._numeric_edit("length")
    assert (widget.components()[1].start_depth_m, widget.components()[1].end_depth_m) == (2.5, 3.5)
    before = widget.components(); widget.end_spin.setValue(1); widget._numeric_edit("end")
    assert widget.components() == before; validate_components(widget.components(), 10)
    toe = BoreholeChargeBuilder(10, None, [], [ChargeComponent("toe", ChargeComponentKind.STEMMING, 8, 10)])
    assert not toe.set_hole_depth(9) and toe.hole_depth() == 10
    assert toe.set_hole_depth(12) and toe.air_intervals() == [(0.0, 8), (10, 12.0)]


def test_real_mouse_drag_moves_lower_handle_and_read_only_disables_editing():
    app(); component = ChargeComponent("a", ChargeComponentKind.STEMMING, 2, 4)
    widget = BoreholeChargeBuilder(10, None, [], [component]); widget.resize(620, 500); widget.show()
    widget.select_component("a"); QApplication.processEvents()
    scene_y = depth_to_scene_y(4, 10, widget._scene_top, widget._scene_height)
    x = widget.view.viewport().width() * .5
    start = widget.view.mapFromScene(QPointF(x, scene_y))
    target_y = depth_to_scene_y(4.6, 10, widget._scene_top, widget._scene_height)
    target = widget.view.mapFromScene(QPointF(x, target_y))
    QTest.mousePress(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(widget.view.viewport(), target); QTest.mouseRelease(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=target)
    assert widget.components()[0].end_depth_m == pytest.approx(4.6)
    widget.set_read_only(True)
    assert not widget.add_button.isEnabled() and not widget.delete_button.isEnabled()
    assert not widget.start_spin.isEnabled() and not widget.product_combo.isEnabled()
    widget.close()


def test_historical_missing_product_remains_visible():
    app(); old = cartridge().snapshot(); old = replace(old, source_product_id=7, name="Old Cartridge", display_color="#123456")
    component = ChargeComponent("old", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, 2, 4, old, .5)
    widget = BoreholeChargeBuilder(10, 100, [], [component]); widget.select_component("old")
    assert widget.product_combo.itemText(0).startswith("Old Cartridge")
    assert widget.components()[0].product_snapshot.display_color == "#123456"
