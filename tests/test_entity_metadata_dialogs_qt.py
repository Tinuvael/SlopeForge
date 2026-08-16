import pytest
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication, QLineEdit

from repositories.domain_repository import SelectableDomain
from ui.dialogs.entity_metadata_dialogs import (
    AssessmentAreaMetadataDialog, ContourMetadataDialog)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def domains():
    return [SelectableDomain(1, "North", 7, 3), SelectableDomain(2, "South", 7, 8)]


def test_contour_metadata_dialog_has_only_name_domain_horizon(qapp):
    dialog = ContourMetadataDialog(domains(), 1, "C-1", 640)
    assert dialog.name.text() == "C-1"
    assert dialog.horizon.value() == 640
    assert dialog.selected_domain == (1, 3)
    assert dialog.findChild(QLineEdit, "name") is dialog.name
    assert dialog.name.objectName() == "name"


def test_assessment_metadata_dialog_has_only_name_and_domain(qapp):
    dialog = AssessmentAreaMetadataDialog(domains()[:1], 1, "Area 1")
    assert dialog.name.text() == "Area 1"
    assert dialog.horizon is None
    assert not dialog.domain.isEnabled()
    assert dialog.selected_domain == (1, 3)