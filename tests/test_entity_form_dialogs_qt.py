from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QToolButton

from repositories.domain_repository import SelectableDomain
from ui.add_dialog import AddDialog
from ui.dialogs.blast_event_dialog import BlastEventDialog
from ui.dialogs.entity_metadata_dialogs import ContourMetadataDialog
from ui.dialogs.rename_entity_dialog import RenameEntityDialog
from ui.project_dialog import ProjectDialog
from ui.widgets.design_system import ChevronDoubleSpinBox


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def assert_standard_actions(dialog, primary):
    assert dialog.objectName() == "StandardEntityDialog"
    assert dialog.cancel_button.property("role") == "secondary"
    assert primary.property("role") == "primary"
    assert primary.isDefault()
    assert dialog.cancel_button.height() == primary.height() == 32
    assert dialog.cancel_button.minimumWidth() == 96
    assert primary.minimumWidth() == 108


def mouse_click(dialog, button, position=None):
    dialog.show()
    QApplication.processEvents()
    QTest.mouseClick(
        button,
        Qt.MouseButton.LeftButton,
        pos=position or button.rect().center(),
    )
    QApplication.processEvents()


def test_project_dialog_retains_fields_path_and_actions(qapp, monkeypatch):
    dialog = ProjectDialog()
    assert dialog.name is not None and dialog.description is not None and dialog.csv_path.isReadOnly()
    assert_standard_actions(dialog, dialog.create_button)
    monkeypatch.setattr(
        "ui.project_dialog.QFileDialog.getOpenFileName",
        lambda *_args: (r"C:\very\long\project\lines.dxf", ""),
    )
    dialog._browse()
    assert dialog.csv_path.text().endswith("lines.dxf")
    dialog.create_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_domain_dialog_retains_name_description_and_actions(qapp):
    dialog = AddDialog("domain")
    dialog.name.setText("North")
    dialog.description.setPlainText("North wall")
    assert dialog.name.text() == "North" and dialog.description.toPlainText() == "North wall"
    assert dialog.description.maximumHeight() == 82
    assert_standard_actions(dialog, dialog.create_button)
    dialog.cancel_button.click()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_blast_event_dialog_contract_and_date_state(qapp):
    service = SimpleNamespace(inspect_event_geometry=lambda *_args: None)
    dialog = BlastEventDialog(service=service)
    assert [dialog.kind.itemText(index) for index in range(2)] == [
        "Production", "Contour blast",
    ]
    assert [dialog.kind.itemData(index) for index in range(2)] == [
        "production", "contour",
    ]
    assert dialog.kind.currentData() == "production"
    assert not dialog.date.isEnabled()
    dialog.has_date.setChecked(True)
    assert dialog.date.isEnabled()
    dialog.name.setText("B-12")
    dialog.csv.setText("geometry.csv")
    dialog.elevation.setValue(620)
    assert dialog.values()["event_type"] == "production"
    assert dialog.values()["csv_path"] == "geometry.csv"
    assert_standard_actions(dialog, dialog.create_button)


def test_metadata_and_rename_dialog_semantic_actions(qapp):
    domains = [SelectableDomain(1, "North", 7, 3), SelectableDomain(2, "South", 7, 8)]
    metadata = ContourMetadataDialog(domains, 1, "C-1", 640)
    assert metadata.selected_domain == (1, 3) and metadata.horizon.value() == 640
    assert_standard_actions(metadata, metadata.save_button)
    rename = RenameEntityDialog("Project", "Pit A")
    assert rename.error_label.objectName() == "FormValidationText"
    assert_standard_actions(rename, rename.save_button)


@pytest.mark.parametrize(
    "factory",
    [
        ProjectDialog,
        lambda: AddDialog("domain"),
        lambda: BlastEventDialog(service=SimpleNamespace(inspect_event_geometry=lambda *_args: None)),
        lambda: RenameEntityDialog("Project", "Pit A"),
        lambda: ContourMetadataDialog([SelectableDomain(1, "North", 7, 3)], 1, "C-1", 640),
    ],
)
def test_standard_cancel_rejects_from_real_mouse_click(qapp, factory):
    dialog = factory()
    accepted = []
    dialog.accepted.connect(lambda: accepted.append(True))
    mouse_click(dialog, dialog.cancel_button)
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not accepted


def test_project_primary_accepts_from_real_mouse_click(qapp):
    dialog = ProjectDialog()
    mouse_click(dialog, dialog.create_button)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cancel_whole_visible_rectangle_is_mouse_clickable(qapp):
    for point_factory in (
        lambda rect: QPoint(1, 1),
        lambda rect: QPoint(rect.right() - 1, 1),
        lambda rect: QPoint(1, rect.bottom() - 1),
        lambda rect: QPoint(rect.right() - 1, rect.bottom() - 1),
    ):
        dialog = ProjectDialog()
        dialog.show()
        QApplication.processEvents()
        mouse_click(dialog, dialog.cancel_button, point_factory(dialog.cancel_button.rect()))
        assert dialog.result() == QDialog.DialogCode.Rejected


def test_escape_rejects_without_accepting(qapp):
    dialog = ProjectDialog()
    dialog.show()
    QApplication.processEvents()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result() == QDialog.DialogCode.Rejected


def _button_test_points(button):
    rect = button.rect()
    return (
        QPoint(2, 2),
        rect.center(),
        QPoint(rect.right() - 2, rect.bottom() - 2),
    )


def test_blast_event_horizon_chevrons_step_across_visible_button_area(qapp):
    dialog = BlastEventDialog(
        service=SimpleNamespace(inspect_event_geometry=lambda *_args: None)
    )
    dialog.show()
    QApplication.processEvents()

    assert isinstance(dialog.elevation, ChevronDoubleSpinBox)
    for point in _button_test_points(dialog.elevation.up_button):
        dialog.elevation.setValue(630)
        QTest.mouseClick(
            dialog.elevation.up_button, Qt.MouseButton.LeftButton, pos=point
        )
        assert dialog.elevation.value() == 631

    for point in _button_test_points(dialog.elevation.down_button):
        dialog.elevation.setValue(631)
        QTest.mouseClick(
            dialog.elevation.down_button, Qt.MouseButton.LeftButton, pos=point
        )
        assert dialog.elevation.value() == 630


def test_horizon_chevrons_own_hit_area_and_respect_non_editable_states(qapp):
    dialog = BlastEventDialog(
        service=SimpleNamespace(inspect_event_geometry=lambda *_args: None)
    )
    dialog.show()
    QApplication.processEvents()
    spinbox = dialog.elevation

    for button in (spinbox.up_button, spinbox.down_button):
        point_in_spinbox = button.mapTo(spinbox, button.rect().center())
        assert spinbox.childAt(point_in_spinbox) is button
        assert isinstance(spinbox.childAt(point_in_spinbox), QToolButton)

    spinbox.setValue(630)
    spinbox.setDisabled(True)
    QTest.mouseClick(spinbox.up_button, Qt.MouseButton.LeftButton)
    assert spinbox.value() == 630
    assert not spinbox.up_button.isEnabled()
    assert not spinbox.down_button.isEnabled()

    spinbox.setEnabled(True)
    spinbox.setReadOnly(True)
    QTest.mouseClick(spinbox.up_button, Qt.MouseButton.LeftButton)
    assert spinbox.value() == 630
    assert not spinbox.up_button.isEnabled()
    assert not spinbox.down_button.isEnabled()


def test_contour_metadata_horizon_uses_chevron_spinbox(qapp):
    domains = [SelectableDomain(1, "North", 7, 3)]
    dialog = ContourMetadataDialog(domains, 1, "C-1", 640)
    dialog.show()
    QApplication.processEvents()

    assert isinstance(dialog.horizon, ChevronDoubleSpinBox)
    QTest.mouseClick(dialog.horizon.up_button, Qt.MouseButton.LeftButton)
    assert dialog.horizon.value() == 641
