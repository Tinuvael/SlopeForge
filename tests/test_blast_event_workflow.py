from datetime import date

import pytest

from application.services.blast_events import BlastEventService, BlastEventValidationError
from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.geometry.types import PlanMultiPoint, PlanPoint, PlanPolygon


def write_dxf(path, lines):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new()
    modelspace = doc.modelspace()
    for points in lines:
        modelspace.add_polyline3d(points)
    doc.saveas(path)


def production_dxf(path, z=620):
    write_dxf(path, [[(0, 0, z), (10, 0, z), (10, 10, z), (0, 0, z)]])


def test_create_production_event(tmp_path):
    source = tmp_path / "block.dxf"
    production_dxf(source)
    state = AssessmentDomainState()
    event = BlastEventService(state).create_event(
        name="Блок", event_type="production", event_date=date.today(), elevation=615, csv_path=source
    )
    assert len(state.blast_events) == 1
    assert isinstance(event.active_geometry_revision().plan_geometry, PlanPolygon)
    assert event.active_geometry_revision().revision_number == 1


def test_create_contour_event_preserves_user_horizon(tmp_path):
    source = tmp_path / "holes.dxf"
    write_dxf(source, [[(0, 0, 650), (0, 0, 620)], [(10, 0, 655), (10, 0, 620)]])
    event = BlastEventService(AssessmentDomainState()).create_event(
        name="Контур", event_type="contour", event_date=date.today(), elevation=640, csv_path=source
    )
    assert event.elevation == 640
    assert isinstance(event.active_geometry_revision().plan_geometry, PlanMultiPoint)


def test_production_preview_uses_median_of_selected_upper_line_only(tmp_path):
    source = tmp_path / "production-levels.dxf"
    write_dxf(source, [
        [(0, 0, 620), (10, 0, 620), (10, 10, 620), (0, 0, 620)],
        [(0, 0, 630), (10, 0, 630), (10, 10, 630.8), (0, 10, 630), (0, 0, 630)],
    ])
    service = BlastEventService(AssessmentDomainState())
    preview = service.inspect_event_geometry("production", source)
    assert preview.suggested_elevation == pytest.approx(630)
    assert preview.selected_source_line_id
    assert preview.selected_line_representative_z == pytest.approx(630)
    event = service.create_event(
        name="Блок", event_type="production", event_date=None,
        elevation=preview.suggested_elevation, csv_path=source,
    )
    assert event.elevation == 630
    assert event.active_geometry_revision().source_geometry[0].source_id == preview.selected_source_line_id
    assert event.active_geometry_revision().elevation == pytest.approx(630.8)


def test_flat_production_preview_suggests_constant_z(tmp_path):
    source = tmp_path / "flat-630.dxf"
    production_dxf(source, 630)
    preview = BlastEventService(AssessmentDomainState()).inspect_event_geometry("production", source)
    assert preview.suggested_elevation == 630


def test_contour_preview_uses_median_accepted_collars_and_ignores_toes_and_flat_lines(tmp_path):
    source = tmp_path / "contour-preview.dxf"
    write_dxf(source, [
        [(0, 0, 630), (0, 0, 590)],
        [(10, 0, 632), (10, 0, 580)],
        [(0, 20, 700), (10, 20, 700)],
    ])
    preview = BlastEventService(AssessmentDomainState()).inspect_event_geometry("contour", source)
    assert preview.suggested_elevation == pytest.approx(631)
    assert preview.accepted_contour_drillhole_count == 2
    assert preview.ignored_flat_contour_line_count == 1


def test_manual_override_wins_over_preview_during_save(tmp_path):
    source = tmp_path / "auto.dxf"
    production_dxf(source, 630)
    service = BlastEventService(AssessmentDomainState())
    assert service.inspect_event_geometry("production", source).suggested_elevation == 630
    event = service.create_event(
        name="Ручной горизонт", event_type="production", event_date=None,
        elevation=628.5, csv_path=source,
    )
    assert event.elevation == 628.5


def test_dialog_new_geometry_and_event_type_refresh_auto_suggestion(tmp_path):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from application.services.blast_events import BlastEventImportPreview
    from ui.dialogs.blast_event_dialog import BlastEventDialog

    class PreviewService:
        def inspect_event_geometry(self, event_type, csv_path):
            base = 640 if event_type == "contour" else 630
            if str(csv_path).endswith("second.dmx"):
                base += 5
            return BlastEventImportPreview(
                base,
                "MultiPoint" if event_type == "contour" else "Polygon",
                selected_source_line_id="2",
                selected_line_representative_z=base,
                accepted_contour_drillhole_count=212,
            )

    app = QApplication.instance() or QApplication([])
    dialog = BlastEventDialog(service=PreviewService())
    dialog.csv.setText(str(tmp_path / "first.dmx"))
    assert dialog._inspect(force_override=True)
    assert dialog.elevation.value() == 630 and not dialog.elevation_is_manual
    dialog.elevation.setValue(628)
    assert dialog.elevation_is_manual
    dialog.csv.setText(str(tmp_path / "second.dmx"))
    dialog._inspect(force_override=True)
    assert dialog.elevation.value() == 635 and not dialog.elevation_is_manual
    contour_index = dialog.kind.findData("contour")
    assert contour_index >= 0
    dialog.kind.setCurrentIndex(contour_index)
    assert dialog.kind.currentData() == "contour"
    assert dialog.elevation.value() == 645 and "212 collars" in dialog.auto_status.text()
    dialog.close()
    assert app


def test_contour_keeps_one_first_maximum_collar_per_imported_line(tmp_path):
    source = tmp_path / "contour.dxf"
    write_dxf(source, [
        [(30, 40, 510), (31, 41, 500)],
        [(10, 20, 500), (99, 99, 500), (11, 21, 490), (12, 22, 480)],
    ])
    event = BlastEventService(AssessmentDomainState()).create_event(
        name="Контур", event_type="contour", event_date=None, elevation=500, csv_path=source
    )
    revision = event.active_geometry_revision()
    assert len(revision.source_geometry) == 2
    assert revision.plan_geometry.points == (PlanPoint(30, 40), PlanPoint(10, 20))


def test_contour_empty_geometry_has_clear_validation_error(tmp_path):
    source = tmp_path / "empty.dxf"
    write_dxf(source, [])
    with pytest.raises(BlastEventValidationError, match="no valid contour drillholes"):
        BlastEventService(AssessmentDomainState()).create_event(
            name="Контур", event_type="contour", event_date=None, elevation=500, csv_path=source
        )


def test_cannot_save_without_geometry(tmp_path):
    with pytest.raises(BlastEventValidationError, match="Could not import geometry file"):
        BlastEventService(AssessmentDomainState()).create_event(
            name="Блок", event_type="production", event_date=None,
            elevation=620, csv_path=tmp_path / "missing.dxf",
        )


def test_reimport_keeps_first_revision_and_makes_revision_two(tmp_path):
    one = tmp_path / "one.dxf"
    two = tmp_path / "two.dxf"
    production_dxf(one, 620)
    production_dxf(two, 621)
    service = BlastEventService(AssessmentDomainState())
    event = service.create_event(
        name="Блок", event_type="production", event_date=None, elevation=620, csv_path=one
    )
    first = event.geometry_revisions[0]
    second = service.reimport_geometry(event, two)
    assert second.revision_number == 2 and second.is_active and not first.is_active
    assert first.source_file_name == "one.dxf" and event.active_geometry_revision_id == second.id


def test_project_line_imports_keep_history_and_can_switch_back(tmp_path):
    first = tmp_path / "first.dxf"
    second = tmp_path / "second.dxf"
    write_dxf(first, [[(0, 0, 600), (10, 0, 600)]])
    write_dxf(second, [[(0, 5, 620), (10, 5, 620)]])
    state = AssessmentDomainState()
    service = ProjectLinesDatasetService(state)
    dataset_1, _ = service.import_dataset(first)
    dataset_2, _ = service.import_dataset(second)
    assert (dataset_1.id, dataset_2.id) == ("D-001", "D-002")
    assert not dataset_1.is_active and dataset_2.is_active
    assert len(state.datasets) == 2
    assert service.set_active("D-001") is dataset_1
    assert dataset_1.is_active and not dataset_2.is_active


def test_available_elevations_excludes_variable_lines(tmp_path):
    source = tmp_path / "levels.dxf"
    write_dxf(source, [
        [(0, 0, 600), (10, 0, 600)],
        [(0, 5, 610), (10, 5, 620)],
    ])
    state = AssessmentDomainState()
    service = ProjectLinesDatasetService(state)
    service.import_dataset(source)
    assert service.available_elevations() == [600.0]
