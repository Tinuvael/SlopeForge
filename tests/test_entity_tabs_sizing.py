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


@pytest.mark.parametrize("window_size", [(1600, 900), (1366, 768)])
def test_wide_hidden_engineering_tabs_do_not_collapse_project_tree(window_size):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_tabs import create_entity_tabs
    from ui.pages.block_overview_widgets import BlockGeometryCard

    app = widgets.QApplication.instance() or widgets.QApplication([])
    window = widgets.QMainWindow()
    central = widgets.QWidget(); window.setCentralWidget(central)
    body = widgets.QHBoxLayout(central)
    project_tree = widgets.QWidget(); project_tree.setObjectName("representativeProjectTree")
    project_tree.setMinimumWidth(240); project_tree.setMaximumWidth(320)
    tabs = create_entity_tabs()
    overview = widgets.QWidget(); overview_layout = widgets.QHBoxLayout(overview)
    overview_layout.addWidget(widgets.QWidget(), 1)
    overview_layout.addWidget(BlockGeometryCard(), 0)
    tabs.addTab(overview, "General information")
    for title in ("Blast design", "Execution fact"):
        wide_scroll = widgets.QScrollArea(); wide_scroll.setWidgetResizable(True)
        content = widgets.QWidget(); content.setMinimumWidth(1800); wide_scroll.setWidget(content)
        tabs.addTab(wide_scroll, title)
    body.addWidget(project_tree, 1); body.addWidget(tabs, 4)
    window.resize(*window_size); window.show(); app.processEvents()

    initial_minimum_width = window.minimumSizeHint().width()
    assert project_tree.width() >= 240
    assert tabs.minimumSizeHint().width() == 0
    assert tabs.geometry().right() <= central.rect().right()
    for index in (1, 2, 0):
        tabs.setCurrentIndex(index); app.processEvents()
        assert project_tree.width() >= 240
        assert window.minimumSizeHint().width() == initial_minimum_width
        assert window.width() == window_size[0]
        assert tabs.geometry().right() <= central.rect().right()

    window.close(); app.processEvents()
