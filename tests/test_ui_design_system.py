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
