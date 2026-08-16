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
    assert header.navigation_button.width() == 36
    assert isinstance(header.navigation_button, QtWidgets.QPushButton)
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


def test_project_tree_header_domain_collapse_and_virtual_sections(monkeypatch):
    from datetime import date
    from ui.widgets import project_tree as module

    app = _app()
    site = SimpleNamespace(id=1, name="Project")
    domain = SimpleNamespace(id=2, name="Domain")
    block = SimpleNamespace(
        id=10, domain_id=2, block_number="B-1", horizon_m=630,
        planned_blast_date=None, status="planned", is_archived=False,
    )
    area = SimpleNamespace(
        id="AA-1", domain_id=2, name="Wall", min_elevation=600,
        max_elevation=620, assessment_date=date.today(), is_archived=False,
    )
    monkeypatch.setattr(module, "SiteRepository", lambda _factory: SimpleNamespace(list_sites=lambda: [site]))
    monkeypatch.setattr(module, "DomainRepository", lambda _factory: SimpleNamespace(list_for_site=lambda _id: [domain]))
    monkeypatch.setattr(module, "BlastBlockRepository", lambda _factory: SimpleNamespace(list_blocks=lambda **_kwargs: [block]))
    monkeypatch.setattr(module, "NavigationRepository", lambda _factory: SimpleNamespace(
        list_areas=lambda _archived: [area], list_contour_events=lambda _archived: []))

    panel = module.ProjectTree(SimpleNamespace(session_factory=object()))
    panel.show(); panel.tree.expandAll(); app.processEvents()
    assert isinstance(panel.tree, module.ProjectTreeWidget)
    assert panel.tree_title.text() == "Project tree"
    assert panel.collapse_button.text() == ""
    assert panel.collapse_button.toolTip() == "Collapse domains"
    assert not panel.collapse_button.icon().isNull()

    def walk(item):
        yield item
        for index in range(item.childCount()):
            yield from walk(item.child(index))

    items = []
    for index in range(panel.tree.topLevelItemCount()):
        items.extend(walk(panel.tree.topLevelItem(index)))
    horizon = next(item for item in items if (item.data(0, Qt.ItemDataRole.UserRole) or {}).get("type") == "horizon")
    interval = next(item for item in items if (item.data(0, Qt.ItemDataRole.UserRole) or {}).get("type") == "interval")
    assert horizon.text(0) == "Horizon 630"
    assert interval.text(0) == "Interval 600–620"
    for section in (horizon, interval):
        assert section.isExpanded()
        assert not (section.flags() & Qt.ItemFlag.ItemIsSelectable)
        assert section.childCount() == 1
        assert panel.tree.visualItemRect(section.child(0)).height() > 0

    assert horizon.child(0).text(0) == "Block B-1"
    assert interval.child(0).text(0) == "Wall"

    horizon.setExpanded(False); interval.setExpanded(False); app.processEvents(); app.processEvents()
    assert horizon.isExpanded() and interval.isExpanded()
    assert panel.tree.visualItemRect(horizon.child(0)).height() > 0
    assert panel.tree.visualItemRect(interval.child(0)).height() > 0

    project = panel.tree.topLevelItem(0)
    domain_item = project.child(0)
    QTest.mouseClick(panel.collapse_button, Qt.MouseButton.LeftButton); app.processEvents()
    assert project.isExpanded()
    assert not domain_item.isExpanded()
    assert horizon.isExpanded() and interval.isExpanded()
    panel.close()
