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


def test_bench_caption_never_contains_python_none():
    app()
    page = Prototype2DPage()
    from prototype_2d.models import BenchSectionDraft
    assert "None" not in page.draft_caption(BenchSectionDraft("U-001", "missing-upper", "missing-lower"))


def test_markers_a_and_b_are_movable():
    from ui.prototype_2d.plan_scene import SegmentMarkerItem
    from PySide6.QtWidgets import QGraphicsItem
    app()
    point = DataminePoint(0, 0, 700, 1)
    assert SegmentMarkerItem("start", point, "A").flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    assert SegmentMarkerItem("end", point, "B").flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


def test_right_panel_has_no_information_group():
    app()
    page = Prototype2DPage()
    assert "Информация" not in [group.title() for group in page.findChildren(QtWidgets.QGroupBox)]


def test_only_selected_bench_segments_are_returned():
    from prototype_2d.models import BenchSectionDraft, LineSegmentSelection
    app()
    page = Prototype2DPage()
    point = lambda x: DataminePoint(x, 0, 700, 1)
    segments = [
        LineSegmentSelection("S1", "L1", 0, 1, [point(0), point(1)], "lower_boundary", 700),
        LineSegmentSelection("S2", "L2", 0, 1, [point(0), point(1)], "upper_boundary", 710),
        LineSegmentSelection("S3", "L3", 0, 1, [point(0), point(1)], "lower_boundary", 720),
        LineSegmentSelection("S4", "L4", 0, 1, [point(0), point(1)], "upper_boundary", 730),
    ]
    page.state = PrototypeState(segments=segments, drafts=[BenchSectionDraft("U-001", "S2", "S1"), BenchSectionDraft("U-002", "S4", "S3")])
    page.controller.selected_bench_id = "U-001"
    assert {item.id for item in page._highlighted_segments()} == {"S1", "S2"}
    page.controller.selected_bench_id = "U-002"
    assert {item.id for item in page._highlighted_segments()} == {"S3", "S4"}


def test_workflow_panel_is_hidden_in_idle_and_shown_when_adding_bench():
    app()
    page = Prototype2DPage()
    assert not page.workflow_panel.isVisible()
    page.state = PrototypeState(lines=[DatamineLine("L", [DataminePoint(0, 0, 700, 1), DataminePoint(1, 0, 700, 2)])])
    page.start_bench_workflow()
    assert page.workflow_panel.isVisible()


def test_new_layout_has_bench_list_and_inspector_without_pit_controls():
    app()
    page = Prototype2DPage()
    assert page.bench_list_panel.add_button.text() == "+ Добавить уступ"
    assert "Граница карьера" not in " ".join(button.text() for button in page.findChildren(QtWidgets.QPushButton))
