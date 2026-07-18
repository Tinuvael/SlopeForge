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
