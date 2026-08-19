import pytest


def test_entity_tabs_keep_outer_size_policy_stable_across_tab_switches():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_tabs import create_entity_tabs

    app = widgets.QApplication.instance() or widgets.QApplication([])
    tabs = create_entity_tabs()
    tabs.addTab(widgets.QWidget(), "Overview")
    tabs.addTab(widgets.QWidget(), "Blast design")
    tabs.addTab(widgets.QWidget(), "Execution fact")

    # Block/Contour/Assessment pages deliberately isolate child size hints from
    # the top-level window. Switching to a very tall Technical Card page must
    # not replace that policy and inflate the maximized Windows window.
    tabs.setSizePolicy(widgets.QSizePolicy.Policy.Expanding, widgets.QSizePolicy.Policy.Ignored)
    expected = tabs.sizePolicy().verticalPolicy()

    for index in (1, 2, 0, 2, 1, 0):
        tabs.setCurrentIndex(index)
        app.processEvents()
        assert tabs.sizePolicy().verticalPolicy() == expected

    tabs.close()
    app.processEvents()
