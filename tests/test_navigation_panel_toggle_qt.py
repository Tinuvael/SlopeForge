from pathlib import Path
from types import SimpleNamespace

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from ui.header import Header
from ui.main_window import MainWindow


def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_header_navigation_toggle_is_compact_and_changes_action_state():
    app = _app()
    header = Header(SimpleNamespace(current_user=SimpleNamespace(can_edit=True)))
    header.show(); app.processEvents()

    assert header.navigation_button.objectName() == "navigationToggleButton"
    assert header.navigation_button.width() == 32
    assert header.navigation_button.toolTip() == "Hide navigation"

    emitted = []
    header.navigation_toggle_requested.connect(lambda: emitted.append(True))
    QTest.mouseClick(header.navigation_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert emitted == [True]

    header.set_navigation_visible(False)
    assert header.navigation_button.toolTip() == "Show navigation"
    assert header.navigation_button.accessibleName() == "Show navigation"
    header.set_navigation_visible(True)
    assert header.navigation_button.toolTip() == "Hide navigation"
    header.close()


def test_main_window_toggle_preserves_same_navigation_widget_and_state():
    app = _app()
    tree = QtWidgets.QWidget()
    tree.setProperty("selection_token", "AA-17")
    tree.setProperty("search_token", "north")
    header = Header(SimpleNamespace(current_user=SimpleNamespace(can_edit=True)))
    shell = SimpleNamespace(_navigation_visible=True, tree=tree, header=header)

    original_tree = shell.tree
    MainWindow._toggle_navigation(shell)
    app.processEvents()
    assert shell.tree is original_tree
    assert shell._navigation_visible is False
    assert tree.isHidden()
    assert tree.property("selection_token") == "AA-17"
    assert tree.property("search_token") == "north"
    assert header.navigation_button.toolTip() == "Show navigation"

    MainWindow._toggle_navigation(shell)
    app.processEvents()
    assert shell.tree is original_tree
    assert shell._navigation_visible is True
    assert not tree.isHidden()
    assert tree.property("selection_token") == "AA-17"
    assert tree.property("search_token") == "north"
    assert header.navigation_button.toolTip() == "Hide navigation"
    tree.close(); header.close()


def test_main_window_wires_header_toggle_without_rebuilding_tree():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")
    assert "self.header.navigation_toggle_requested.connect(self._toggle_navigation)" in source
    assert "self.tree.setVisible(self._navigation_visible)" in source
    toggle = source[source.index("def _toggle_navigation"):source.index("def _show", source.index("def _toggle_navigation"))]
    assert "ProjectTree(" not in toggle
    assert "load_data(" not in toggle
    assert "reload_filters(" not in toggle
    assert "set_search_query(" not in toggle
