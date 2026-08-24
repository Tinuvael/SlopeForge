from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_dark_theme_uses_one_full_row_selection_for_assessment_links() -> None:
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.application_theme import apply_application_theme
    from ui.pages.assessment_area_page import AssessmentLinkListItem
    from ui.theme_compat import install_legacy_entity_page_theme_cleanup

    app = _app()
    install_legacy_entity_page_theme_cleanup(app)
    apply_application_theme(app, "dark")

    owner = QtWidgets.QListWidget()
    links = []
    for index, status in enumerate(("confirmed", "excluded"), start=1):
        event = SimpleNamespace(name=f"Event {index}", event_type="production", elevation=620)
        link = SimpleNamespace(
            status=status,
            source="automatic",
            geometry_revision_id=f"R{index}",
        )
        widget = AssessmentLinkListItem(event, link, stale=False)
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(widget.sizeHint())
        owner.addItem(item)
        owner.setItemWidget(item, widget)
        links.append(widget)

    owner.show()
    app.processEvents()

    owner.setCurrentRow(0)
    app.processEvents()
    assert "QListWidget::item:selected" in owner.styleSheet()
    assert "background: transparent" in owner.styleSheet()
    assert "#79b9ee" in links[0].styleSheet()
    assert "#79b9ee" not in links[1].styleSheet()

    owner.setCurrentRow(1)
    app.processEvents()
    assert "#79b9ee" not in links[0].styleSheet()
    assert "#79b9ee" in links[1].styleSheet()

    apply_application_theme(app, "light")
    app.processEvents()
    assert "#2563a6" not in links[0].styleSheet()
    assert "#2563a6" in links[1].styleSheet()
    owner.close()


def test_dark_theme_overrides_windows_white_complex_inputs_in_engineering_contexts() -> None:
    QtCore = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.application_theme import apply_application_theme
    from ui.theme_compat import install_legacy_entity_page_theme_cleanup
    from ui.widgets.design_system import configure_standard_dialog

    app = _app()
    install_legacy_entity_page_theme_cleanup(app)
    apply_application_theme(app, "dark")

    dialog = QtWidgets.QDialog()
    root = configure_standard_dialog(dialog)
    combo = QtWidgets.QComboBox()
    combo.addItem("Production")
    date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
    date.setEnabled(False)
    root.addWidget(combo)
    root.addWidget(date)

    engineering = QtWidgets.QWidget()
    engineering.setObjectName("EngineeringWorkspace")
    engineering_layout = QtWidgets.QVBoxLayout(engineering)
    preset = QtWidgets.QComboBox()
    preset.addItem("Preset")
    engineering_layout.addWidget(preset)

    geomechanics = QtWidgets.QWidget()
    geomechanics.setObjectName("geomechanicsWorkspace")
    geomechanics.setStyleSheet(
        "QLineEdit { background: white; border: 1px solid #d6dbe3; }"
    )
    geomechanics_layout = QtWidgets.QVBoxLayout(geomechanics)
    lithology = QtWidgets.QLineEdit("Diorite")
    rating = QtWidgets.QComboBox()
    rating.addItem("1")
    geomechanics_layout.addWidget(lithology)
    geomechanics_layout.addWidget(rating)

    for widget in (dialog, engineering, geomechanics):
        widget.show()
    app.processEvents()

    for widget in (combo, date, preset, lithology, rating):
        assert widget.property("slopeforgeDarkInputManaged") is True
        assert "#202630" in widget.styleSheet()
        assert "#252c36" in widget.styleSheet()
    assert geomechanics.styleSheet() == ""

    apply_application_theme(app, "light")
    app.processEvents()
    for widget in (combo, date, preset, lithology, rating):
        assert not bool(widget.property("slopeforgeDarkInputManaged"))
        assert "#202630" not in widget.styleSheet()

    dialog.close()
    engineering.close()
    geomechanics.close()
