from datetime import datetime, timezone

import pytest

from domain.blasting.entities import BlastEvent, BlastEventGeometryRevision
from domain.blasting.technical_card import new_technical_card
from domain.geometry.types import PlanPoint, PlanPolygon


def _production_event():
    polygon = PlanPolygon((
        PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 5),
        PlanPoint(0, 5), PlanPoint(0, 0),
    ))
    event = BlastEvent("BE-GEO-UI", "Block", "production", None, 620)
    event.geometry_revisions.append(BlastEventGeometryRevision(
        "G-GEO-UI", event.id, 1, datetime.now(timezone.utc),
        "source.csv", [], polygon, 620, True,
    ))
    event.active_geometry_revision_id = "G-GEO-UI"
    return event


def _dialog():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog

    app = widgets.QApplication.instance() or widgets.QApplication([])
    event = _production_event(); card, revision = new_technical_card(event)
    dialog = TechnicalCardDialog(event, card, revision, lambda *_: None, domain_name="North")
    workspace = dialog.findChild(widgets.QWidget, "geomechanicsWorkspace")
    dialog.tabs.setCurrentWidget(workspace)
    dialog.resize(1180, 720); dialog.show(); app.processEvents()
    return widgets, app, dialog, workspace


def test_engineering_spinbox_visible_arrow_zone_steps_reliably():
    qtcore = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    qttest = pytest.importorskip("PySide6.QtTest", exc_type=ImportError)
    _, app, dialog, _ = _dialog()

    spin = dialog.gsi
    spin.setValue(spin.minimum())  # empty sentinel below the valid GSI range
    app.processEvents()

    up_point = qtcore.QPoint(spin.width() - 6, max(2, spin.height() // 4))
    qttest.QTest.mouseClick(spin, qtcore.Qt.MouseButton.LeftButton, pos=up_point)
    assert spin.value() == 1

    down_point = qtcore.QPoint(spin.width() - 6, min(spin.height() - 2, spin.height() * 3 // 4))
    qttest.QTest.mouseClick(spin, qtcore.Qt.MouseButton.LeftButton, pos=down_point)
    assert spin.value() == spin.minimum()

    dialog.close(); app.processEvents()


def test_geomechanics_workspace_uses_four_quadrants_and_compact_notes_row():
    widgets, app, dialog, workspace = _dialog()

    rock = workspace.findChild(widgets.QWidget, "rockMassSection")
    joints = workspace.findChild(widgets.QWidget, "jointSetsSection")
    qsystem = workspace.findChild(widgets.QWidget, "qSystemSection")
    screening = workspace.findChild(widgets.QWidget, "structuralScreeningSection")
    notes = workspace.findChild(widgets.QWidget, "geomechanicsNotes")

    assert all((rock, joints, qsystem, screening, notes))
    assert rock.x() < qsystem.x()
    assert joints.x() < screening.x()
    assert rock.y() < joints.y()
    assert qsystem.y() < screening.y()
    assert notes.y() > joints.y() and notes.y() > screening.y()

    notes_label = notes.findChild(widgets.QLabel, "EngineeringInlineLabel")
    assert notes_label is not None
    assert notes_label.parentWidget() is notes
    assert dialog.geo_notes.parentWidget() is notes

    dialog.close(); app.processEvents()
