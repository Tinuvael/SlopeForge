import pytest


def test_entity_tabs_expand_viewport_without_propagating_tall_page_hint():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_tabs import create_entity_tabs

    app = widgets.QApplication.instance() or widgets.QApplication([])
    host = widgets.QWidget()
    host.resize(900, 700)
    layout = widgets.QVBoxLayout(host)

    tabs = create_entity_tabs()
    assert tabs.property("entityTabs") is True
    assert tabs.documentMode() is True
    # Operational pages still contain this legacy call. The shared widget must
    # correct it before presentation rather than changing policy per tab.
    tabs.setSizePolicy(widgets.QSizePolicy.Policy.Expanding, widgets.QSizePolicy.Policy.Ignored)

    overview = widgets.QWidget()
    tall_page = widgets.QWidget()
    tall_page.setMinimumHeight(1600)
    execution = widgets.QWidget()
    execution.setMinimumHeight(1800)
    tabs.addTab(overview, "Overview")
    tabs.addTab(tall_page, "Blast design")
    tabs.addTab(execution, "Execution fact")

    actions = widgets.QWidget()
    actions.setFixedHeight(32)
    layout.addWidget(tabs, 1)
    layout.addWidget(actions, 0)
    host.show()
    app.processEvents()

    assert tabs.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert tabs.sizeHint().height() == 0
    assert tabs.minimumSizeHint().height() == 0
    assert tabs.height() > 500

    initial_host_height = host.height()
    for index in (1, 2, 0, 2, 1, 0):
        tabs.setCurrentIndex(index)
        app.processEvents()
        assert tabs.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
        assert tabs.sizeHint().height() == 0
        assert tabs.minimumSizeHint().height() == 0
        assert tabs.height() > 500
        assert host.height() == initial_host_height

    host.close()
    app.processEvents()
