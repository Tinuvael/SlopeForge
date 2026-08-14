from dataclasses import replace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtWidgets import QDialogButtonBox, QGraphicsEllipseItem, QGraphicsTextItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ExplosiveProduct, ExplosiveProductKind,
    validate_components,
)
from ui.widgets.borehole_charge_builder import (
    BoreholeChargeBuilder, depth_to_scene_y, find_snapped_insertion_interval,
    scene_y_to_depth, snap_depth,
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
    assert find_snapped_insertion_interval((1.05, 1.15)) is None
    assert find_snapped_insertion_interval((1.04, 1.25)) == (1.1, 1.2)


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


def test_legend_escapes_product_name_markup():
    app(); product = replace(cartridge(), name="A < B & C")
    component = ChargeComponent("safe", ChargeComponentKind.CARTRIDGE_EXPLOSIVE,
                                2, 4, product.snapshot(), .5)
    widget = BoreholeChargeBuilder(10, 100, [product], [component])
    assert "A &lt; B &amp; C" in widget.legend.text()


def test_off_grid_air_gap_never_creates_an_out_of_gap_component():
    app()
    occupied = [
        ChargeComponent("before", ChargeComponentKind.STEMMING, 0, 1.05),
        ChargeComponent("after", ChargeComponentKind.STEMMING, 1.15, 2),
    ]
    widget = BoreholeChargeBuilder(2, None, [], occupied)
    changes = []; widget.components_changed.connect(changes.append)
    widget.select_air((1.05, 1.15)); before = widget.components()
    assert not widget.add_stemming()
    assert widget.components() == before and changes == []
    validate_components(widget.components(), 2)

    occupied[0] = replace(occupied[0], end_depth_m=1.04)
    occupied[1] = replace(occupied[1], start_depth_m=1.25)
    widget.set_components(occupied); widget.select_air((1.04, 1.25))
    assert widget.add_stemming()
    inserted = next(component for component in widget.components() if component.id not in {"before", "after"})
    assert (inserted.start_depth_m, inserted.end_depth_m) == (1.1, 1.2)
    assert len(changes) == 1
    validate_components(widget.components(), 2)


def test_cartridge_without_default_pitch_requires_explicit_value():
    app(); product = replace(cartridge(), default_pitch_m=None)
    widget = BoreholeChargeBuilder(2, 100, [product], [])
    changes = []; widget.components_changed.connect(changes.append)

    def cancel_dialog():
        dialog = QApplication.activeModalWidget()
        assert dialog.pitch_spin.text() == "Not set"
        QTest.mouseClick(
            dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel),
            Qt.MouseButton.LeftButton)

    QTimer.singleShot(0, cancel_dialog)
    assert not widget.add_component(ChargeComponentKind.CARTRIDGE_EXPLOSIVE, product)
    assert widget.components() == [] and changes == []

    def enter_explicit_pitch():
        dialog = QApplication.activeModalWidget()
        assert dialog.pitch_spin.text() == "Not set"
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert dialog.isVisible()
        assert dialog.feedback.text() == "Pitch is required"
        assert widget.components() == [] and changes == []
        dialog.pitch_spin.setValue(.35)
        QTest.mouseClick(ok, Qt.MouseButton.LeftButton)

    QTimer.singleShot(0, enter_explicit_pitch)
    assert widget.add_component(ChargeComponentKind.CARTRIDGE_EXPLOSIVE, product)
    assert widget.components()[0].cartridge_pitch_m == .35
    assert len(changes) == 1


def _click_item(widget, item):
    point = widget.view.mapFromScene(item.sceneBoundingRect().center())
    QTest.mouseClick(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QApplication.processEvents()


def test_cartridge_marker_component_label_and_air_label_are_click_targets():
    app(); product = cartridge()
    cartridge_deck = ChargeComponent(
        "deck", ChargeComponentKind.CARTRIDGE_EXPLOSIVE, 2, 5,
        product.snapshot(), .5)
    stemming = ChargeComponent("stemming", ChargeComponentKind.STEMMING, 6, 9)
    widget = BoreholeChargeBuilder(10, 100, [product], [cartridge_deck, stemming])
    widget.resize(620, 520); widget.show(); QApplication.processEvents()

    marker = next(item for item in widget.view.scene().items()
                  if isinstance(item, QGraphicsEllipseItem) and item.data(1) == "deck")
    _click_item(widget, marker)
    assert widget._selected_component_id == "deck"

    component_label = next(item for item in widget.view.scene().items()
                           if isinstance(item, QGraphicsTextItem)
                           and item.data(1) == "stemming")
    _click_item(widget, component_label)
    assert widget._selected_component_id == "stemming"

    air_label = next(item for item in widget.view.scene().items()
                     if isinstance(item, QGraphicsTextItem) and item.data(0) == "air")
    expected_gap = tuple(air_label.data(1)); _click_item(widget, air_label)
    assert widget._selected_air == expected_gap and widget._selected_component_id is None
    widget.close()


def test_real_body_drag_accumulates_small_pointer_moves():
    app(); component = ChargeComponent("body", ChargeComponentKind.STEMMING, 2, 4)
    widget = BoreholeChargeBuilder(10, None, [], [component]); widget.resize(620, 520); widget.show()
    QApplication.processEvents()
    x = widget.view.sceneRect().width() * .46 + 40
    origin_y = depth_to_scene_y(3, 10, widget._scene_top, widget._scene_height)
    origin = widget.view.mapFromScene(QPointF(x, origin_y))
    QTest.mousePress(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=origin)
    for delta in (.04, .08, .12, .16, .20, .24, .28, .32, .36, .40):
        y = depth_to_scene_y(3 + delta, 10, widget._scene_top, widget._scene_height)
        QTest.mouseMove(widget.view.viewport(), widget.view.mapFromScene(QPointF(x, y)))
    target = widget.view.mapFromScene(QPointF(
        x, depth_to_scene_y(3.4, 10, widget._scene_top, widget._scene_height)))
    QTest.mouseRelease(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=target)
    assert (widget.components()[0].start_depth_m,
            widget.components()[0].end_depth_m) == pytest.approx((2.4, 4.4))
    widget.close()
