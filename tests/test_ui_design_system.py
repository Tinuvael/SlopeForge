import pytest


def test_shared_card_and_semantic_properties_are_stable():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.widgets.design_system import CardFrame, set_button_role, set_status_role

    app = widgets.QApplication.instance() or widgets.QApplication([])
    card = CardFrame("General information")
    button = set_button_role(widgets.QPushButton("Save"), "primary")
    badge = set_status_role(widgets.QLabel("Planned"), "info")

    assert card.objectName() == "CardFrame"
    assert card.layout.contentsMargins().left() == 14
    assert card.layout.spacing() == 8
    assert button.property("role") == "primary"
    assert badge.objectName() == "StatusBadge"
    assert badge.property("statusRole") == "info"

    card.close()
    button.close()
    badge.close()
    app.processEvents()


def test_unknown_button_role_is_rejected():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.widgets.design_system import set_button_role

    app = widgets.QApplication.instance() or widgets.QApplication([])
    with pytest.raises(ValueError):
        set_button_role(widgets.QPushButton("Unknown"), "emphasis")
    app.processEvents()


def test_standard_table_contract_and_contrast_icon():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtGui import QIcon
    from ui.widgets.design_system import configure_standard_table, high_contrast_icon

    app = widgets.QApplication.instance() or widgets.QApplication([])
    table = configure_standard_table(widgets.QTableWidget(1, 1))
    assert table.objectName() == "StandardTable"
    assert table.verticalHeader().isHidden()
    assert table.verticalHeader().defaultSectionSize() == 34
    assert table.selectionBehavior() == widgets.QAbstractItemView.SelectionBehavior.SelectRows
    assert isinstance(high_contrast_icon(QIcon()), QIcon)
    table.close()
    app.processEvents()
