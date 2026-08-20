from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication, QDialog

from repositories.domain_repository import SelectableDomain
from ui.add_dialog import AddDialog
from ui.dialogs.blast_event_dialog import BlastEventDialog
from ui.dialogs.entity_metadata_dialogs import ContourMetadataDialog
from ui.dialogs.rename_entity_dialog import RenameEntityDialog
from ui.project_dialog import ProjectDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def assert_standard_actions(dialog, primary):
    assert dialog.objectName() == "StandardEntityDialog"
    assert dialog.cancel_button.property("role") == "secondary"
    assert primary.property("role") == "primary"
    assert primary.isDefault()


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
    assert_standard_actions(dialog, dialog.create_button)
    dialog.cancel_button.click()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_blast_event_dialog_contract_and_date_state(qapp):
    service = SimpleNamespace(inspect_event_geometry=lambda *_args: None)
    dialog = BlastEventDialog(service=service)
    assert dialog.kind.itemText(0) == "production" and dialog.kind.itemText(1) == "contour"
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
