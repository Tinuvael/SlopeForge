import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

QtCore = pytest.importorskip("PySide6.QtCore", reason="PySide6 Qt libraries are unavailable", exc_type=ImportError)
QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 Qt libraries are unavailable", exc_type=ImportError)
Qt = QtCore.Qt
QApplication = QtWidgets.QApplication

from prototype_2d.models import DatamineLine, DataminePoint, PrototypeState
from ui.prototype_2d.prototype_page import Prototype2DPage
from ui.prototype_2d.window import Prototype2DWindow


def app():
    return QApplication.instance() or QApplication([])


def test_window_has_normal_window_flags_and_close_button(qtbot=None):
    app()
    window = Prototype2DWindow()
    assert window.windowFlags() & Qt.WindowType.Window
    assert window.minimumWidth() >= 1000
    closed = []
    window.closed.connect(lambda: closed.append(True))
    window.close()
    assert closed


def test_working_horizon_keeps_context_lines_in_state_and_only_hides_visually():
    app()
    page = Prototype2DPage()
    page.state = PrototypeState(lines=[
        DatamineLine("H700", [DataminePoint(0, 0, 700, 1), DataminePoint(1, 0, 700, 2)]),
        DatamineLine("H710", [DataminePoint(0, 1, 710, 1), DataminePoint(1, 1, 710, 2)]),
    ])
    page.refresh_lists()
    page.horizon_combo.setCurrentText("700.0")
    page.only_horizon_check.setChecked(False)
    page.refresh_scene()
    assert len(page.state.lines) == 2
    assert set(page.scene._items) == {"H700", "H710"}
    page.only_horizon_check.setChecked(True)
    page.refresh_scene()
    assert len(page.state.lines) == 2
    assert set(page.scene._items) == {"H700"}


def test_default_splitter_gives_plan_most_of_window_width():
    app()
    page = Prototype2DPage()
    sizes = page.splitter.sizes()
    assert sizes[0] > sizes[1] * 2


def test_escape_clears_horizon_and_selected_bench_without_removing_state():
    app()
    page = Prototype2DPage()
    page.state = PrototypeState(lines=[
        DatamineLine("H700", [DataminePoint(0, 0, 700, 1), DataminePoint(1, 0, 700, 2)]),
        DatamineLine("H710", [DataminePoint(0, 1, 710, 1), DataminePoint(1, 1, 710, 2)]),
    ])
    page.refresh_lists()
    page.horizon_combo.setCurrentText("700.0")
    page.controller.selected_line_id = "H700"
    page.clear_selection()
    assert page.horizon_combo.currentIndex() == 0
    assert page.controller.selected_line_id is None
    assert len(page.state.lines) == 2


def test_pit_boundary_can_be_toggled_from_selected_line():
    app()
    page = Prototype2DPage()
    page.state = PrototypeState(lines=[DatamineLine("PIT", [DataminePoint(0, 0, 700, 1), DataminePoint(1, 0, 700, 2)])])
    page.controller.selected_line_id = "PIT"
    page.update_line_info()
    page.toggle_pit_boundary()
    assert page.state.lines[0].semantic_role == "pit_boundary"
    page.toggle_pit_boundary()
    assert page.state.lines[0].semantic_role == "normal"


def test_advanced_panel_has_no_endpoint_autoconnect_controls():
    app()
    page = Prototype2DPage()
    assert not hasattr(page, "auto_connect_check")
    assert not hasattr(page, "connection_tolerance")
