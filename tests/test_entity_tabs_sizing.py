import pytest


def test_entity_tabs_ignore_overview_height_but_expand_working_tabs():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_tabs import create_entity_tabs

    app = widgets.QApplication.instance() or widgets.QApplication([])
    tabs = create_entity_tabs()
    tabs.addTab(widgets.QWidget(), "Overview")
    tabs.addTab(widgets.QWidget(), "Blast design")
    tabs.addTab(widgets.QWidget(), "Execution fact")

    assert tabs.currentIndex() == 0
    assert tabs.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Ignored

    tabs.setCurrentIndex(1)
    assert tabs.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding

    tabs.setCurrentIndex(2)
    assert tabs.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding

    tabs.setCurrentIndex(0)
    assert tabs.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Ignored

    tabs.close()
    app.processEvents()
