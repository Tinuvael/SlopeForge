from datetime import date, datetime, timezone
import json

import pytest

from prototype_2d.blast_event_service import BlastEventService, BlastEventValidationError
from prototype_2d.blast_event_storage import load_blast_event_state, save_blast_event_state
from prototype_2d.csv_importer import detect_columns, import_datamine_csv
from prototype_2d.domain import AssessmentDomainState, PlanMultiPoint, PlanPoint, PlanPolygon
from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService


def write_csv(path, rows):
    path.write_text("XP,YP,ZP,SID,PTN\n" + "\n".join(
        f"{x},{y},{z},{line},{order}" for x, y, z, line, order in rows
    ), encoding="utf-8")


def production_csv(path, z=620):
    write_csv(path, [(0,0,z,"top",1),(10,0,z,"top",2),(10,10,z,"top",3),(0,0,z,"top",4)])


def test_create_production_event(tmp_path):
    source=tmp_path/"block.csv"; production_csv(source); state=AssessmentDomainState()
    event=BlastEventService(state).create_event(name="Блок",event_type="production",event_date=date.today(),elevation=615,csv_path=source)
    assert len(state.blast_events)==1 and isinstance(event.active_geometry_revision().plan_geometry, PlanPolygon)
    assert event.active_geometry_revision().revision_number == 1


def test_create_contour_event_preserves_user_horizon(tmp_path):
    source=tmp_path/"holes.csv"; write_csv(source, [(0,0,650,"h1",1),(0,0,620,"h1",2),(10,0,655,"h2",1),(10,0,620,"h2",2)])
    event=BlastEventService(AssessmentDomainState()).create_event(name="Контур",event_type="contour",event_date=date.today(),elevation=640,csv_path=source)
    assert event.elevation == 640 and isinstance(event.active_geometry_revision().plan_geometry, PlanMultiPoint)


def test_production_preview_uses_median_of_selected_upper_line_only(tmp_path):
    source = tmp_path / "production-levels.csv"
    write_csv(source, [
        (0, 0, 620, "lower", 1), (10, 0, 620, "lower", 2),
        (10, 10, 620, "lower", 3), (0, 0, 620, "lower", 4),
        (0, 0, 630, "upper", 1), (10, 0, 630, "upper", 2),
        (10, 10, 630.8, "upper", 3), (0, 10, 630, "upper", 4), (0, 0, 630, "upper", 5),
    ])
    service = BlastEventService(AssessmentDomainState())
    preview = service.inspect_event_geometry("production", source)
    assert preview.suggested_elevation == pytest.approx(630)
    assert preview.selected_source_line_id == "upper"
    assert preview.selected_line_representative_z == pytest.approx(630)
    event = service.create_event(name="Блок", event_type="production", event_date=None,
                                 elevation=preview.suggested_elevation, csv_path=source)
    assert event.elevation == 630
    assert event.active_geometry_revision().source_geometry[0].source_id == "upper"
    assert event.active_geometry_revision().elevation == pytest.approx(630.8)


def test_flat_production_preview_suggests_constant_z(tmp_path):
    source = tmp_path / "flat-630.csv"; production_csv(source, 630)
    preview = BlastEventService(AssessmentDomainState()).inspect_event_geometry("production", source)
    assert preview.suggested_elevation == 630


def test_contour_preview_uses_median_accepted_collars_and_ignores_toes_and_flat_lines(tmp_path):
    source = tmp_path / "contour-preview.csv"
    write_csv(source, [
        (0, 0, 630, "hole-1", 1), (0, 0, 590, "hole-1", 2),
        (10, 0, 632, "hole-2", 1), (10, 0, 580, "hole-2", 2),
        (0, 20, 700, "marker", 1), (10, 20, 700, "marker", 2),
    ])
    preview = BlastEventService(AssessmentDomainState()).inspect_event_geometry("contour", source)
    assert preview.suggested_elevation == pytest.approx(631)
    assert preview.accepted_contour_drillhole_count == 2
    assert preview.ignored_flat_contour_line_count == 1


def test_manual_override_wins_over_preview_during_save(tmp_path):
    source = tmp_path / "auto.csv"; production_csv(source, 630)
    service = BlastEventService(AssessmentDomainState())
    assert service.inspect_event_geometry("production", source).suggested_elevation == 630
    event = service.create_event(name="Ручной горизонт", event_type="production", event_date=None,
                                 elevation=628.5, csv_path=source)
    assert event.elevation == 628.5


def test_dialog_new_csv_and_event_type_refresh_auto_suggestion(tmp_path):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from prototype_2d.blast_event_service import BlastEventImportPreview
    from ui.prototype_2d.blast_event_window import BlastEventDialog

    class PreviewService:
        def inspect_event_geometry(self, event_type, csv_path):
            base = 640 if event_type == "contour" else 630
            if str(csv_path).endswith("second.csv"): base += 5
            return BlastEventImportPreview(base, "MultiPoint" if event_type == "contour" else "Polygon",
                selected_source_line_id="2", selected_line_representative_z=base,
                accepted_contour_drillhole_count=212)

    app = QApplication.instance() or QApplication([])
    dialog = BlastEventDialog(service=PreviewService())
    dialog.csv.setText(str(tmp_path / "first.csv")); assert dialog._inspect(force_override=True)
    assert dialog.elevation.value() == 630 and not dialog.elevation_is_manual
    dialog.elevation.setValue(628); assert dialog.elevation_is_manual
    dialog.csv.setText(str(tmp_path / "second.csv")); dialog._inspect(force_override=True)
    assert dialog.elevation.value() == 635 and not dialog.elevation_is_manual
    dialog.kind.setCurrentText("contour")
    assert dialog.elevation.value() == 645 and "212 устьев" in dialog.auto_status.text()
    dialog.close(); assert app


def test_contour_groups_by_sid_and_keeps_one_first_maximum_collar(tmp_path):
    source = tmp_path / "contour.csv"
    source.write_text(
        "XP,YP,ZP,SID,PTN\n"
        "31,41,500,102,2\n"
        "11,21,490,101.0,2\n"
        "10,20,500,101,1\n"
        "99,99,500,101.00,3\n"
        "30,40,510,102,1\n"
        "12,22,480,101,4\n",
        encoding="utf-8",
    )
    imported = import_datamine_csv(source)
    assert [line.source_id for line in imported.lines] == ["102", "101"]
    assert imported.summary.line_count == 2

    event = BlastEventService(AssessmentDomainState()).create_event(
        name="Контур", event_type="contour", event_date=None, elevation=500, csv_path=source
    )
    revision = event.active_geometry_revision()
    assert len(revision.source_geometry) == imported.summary.line_count
    assert revision.plan_geometry.points == (PlanPoint(30, 40), PlanPoint(10, 20))


def test_automatic_detection_and_import_prefer_sid_over_ptn(tmp_path):
    headers = ["XP", "YP", "ZP", "PTN", "SID"]
    assert detect_columns(headers)["LINE_ID"] == "SID"
    source = tmp_path / "sid.csv"
    source.write_text("XP,YP,ZP,PTN,SID\n0,0,500,1,7\n1,1,490,2,7\n", encoding="utf-8")
    # Even a stale/manual PTN mapping must not override an available SID.
    result = import_datamine_csv(source, {"X": "XP", "Y": "YP", "Z": "ZP", "LINE_ID": "PTN"})
    assert result.summary.column_mapping["LINE_ID"] == "SID"
    assert len(result.lines) == 1 and len(result.lines[0].points) == 2


def test_contour_empty_rows_have_clear_validation_error(tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text("XP,YP,ZP,SID,PTN\n", encoding="utf-8")
    with pytest.raises(BlastEventValidationError, match="валидных контурных скважин"):
        BlastEventService(AssessmentDomainState()).create_event(
            name="Контур", event_type="contour", event_date=None, elevation=500, csv_path=source
        )


def test_cannot_save_without_geometry(tmp_path):
    with pytest.raises(BlastEventValidationError, match="CSV"):
        BlastEventService(AssessmentDomainState()).create_event(name="Блок",event_type="production",event_date=None,elevation=620,csv_path=tmp_path/"missing.csv")


def test_reimport_keeps_first_revision_and_makes_revision_two(tmp_path):
    one=tmp_path/"one.csv"; two=tmp_path/"two.csv"; production_csv(one,620); production_csv(two,621); service=BlastEventService(AssessmentDomainState())
    event=service.create_event(name="Блок",event_type="production",event_date=None,elevation=620,csv_path=one); first=event.geometry_revisions[0]
    second=service.reimport_geometry(event,two)
    assert second.revision_number == 2 and second.is_active and not first.is_active
    assert first.source_file_name == "one.csv" and event.active_geometry_revision_id == second.id


def test_archive_restore_and_json_round_trip(tmp_path):
    source=tmp_path/"block.csv"; production_csv(source); state=AssessmentDomainState(); event=BlastEventService(state).create_event(name="Блок",event_type="production",event_date=None,elevation=620,csv_path=source)
    event.archive("проверка"); target=save_blast_event_state(state,tmp_path/"events.json"); restored=load_blast_event_state(target)
    assert restored.blast_events[0].is_archived and restored.blast_events[0].active_geometry_revision_id == event.active_geometry_revision_id
    restored.blast_events[0].restore(); assert not restored.blast_events[0].is_archived


def test_main_window_embeds_assessment_instead_of_standalone_entry_point():
    source = __import__('pathlib').Path('ui/main_window.py').read_text(encoding='utf-8')
    assert 'Blast Events Prototype' not in source
    assert 'open_blast_events_prototype' not in source
    assert 'AssessmentWorkspacePage' in source
    assert '2D Plan Prototype' not in source
    assert 'Prototype2DWindow' not in source


def test_project_line_imports_keep_history_and_can_switch_back(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    write_csv(first, [(0, 0, 600, "a", 1), (10, 0, 600, "a", 2)])
    write_csv(second, [(0, 5, 620, "b", 1), (10, 5, 620, "b", 2)])
    state = AssessmentDomainState()
    service = ProjectLinesDatasetService(state)
    dataset_1, _ = service.import_dataset(first)
    dataset_2, _ = service.import_dataset(second)
    assert (dataset_1.id, dataset_2.id) == ("D-001", "D-002")
    assert not dataset_1.is_active and dataset_2.is_active
    assert len(state.datasets) == 2
    assert service.set_active("D-001") is dataset_1
    assert dataset_1.is_active and not dataset_2.is_active


def test_project_lines_json_round_trip_and_old_json_compatibility(tmp_path):
    source = tmp_path / "lines.csv"
    write_csv(source, [(1, 2, 600, "a", 1), (3, 4, 600, "a", 2)])
    state = AssessmentDomainState()
    ProjectLinesDatasetService(state).import_dataset(
        source, imported_at=datetime(2026, 7, 25, tzinfo=timezone.utc)
    )
    restored = load_blast_event_state(save_blast_event_state(state, tmp_path / "state.json"))
    assert restored.to_dict() == state.to_dict()
    old_path = tmp_path / "old.json"
    old_path.write_text(json.dumps({"blast_events": [], "assessment_areas": []}), encoding="utf-8")
    assert load_blast_event_state(old_path).datasets == []


def test_available_elevations_excludes_variable_lines(tmp_path):
    source = tmp_path / "levels.csv"
    write_csv(source, [
        (0, 0, 600, "horizontal", 1), (10, 0, 600, "horizontal", 2),
        (0, 5, 610, "variable", 1), (10, 5, 620, "variable", 2),
    ])
    state = AssessmentDomainState()
    service = ProjectLinesDatasetService(state)
    service.import_dataset(source)
    assert service.available_elevations() == [600.0]


def test_blast_window_draws_toggleable_background_below_event(tmp_path):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from ui.prototype_2d.blast_event_window import BLAST_GEOMETRY_ROLE, PROJECT_LINE_ROLE, BlastEventWindow

    app = QApplication.instance() or QApplication([])
    project = tmp_path / "project.csv"
    block = tmp_path / "block.csv"
    write_csv(project, [(-20, 0, 600, "design", 1), (30, 0, 600, "design", 2)])
    production_csv(block)
    state = AssessmentDomainState()
    ProjectLinesDatasetService(state).import_dataset(project)
    event = BlastEventService(state).create_event(
        name="Блок", event_type="production", event_date=None, elevation=620, csv_path=block
    )
    storage = save_blast_event_state(state, tmp_path / "window.json")
    window = BlastEventWindow(storage_path=storage)
    window.selected_event = event = window.state.blast_events[0]
    window.draw_geometry()
    project_items = [item for item in window.scene.items() if item.data(PROJECT_LINE_ROLE)]
    blast_items = [item for item in window.scene.items() if item.data(BLAST_GEOMETRY_ROLE)]
    assert project_items and blast_items
    assert max(item.zValue() for item in project_items) < min(item.zValue() for item in blast_items)
    combined = window.scene.itemsBoundingRect()
    window.lines_checkbox.setChecked(False)
    assert not [item for item in window.scene.items() if item.data(PROJECT_LINE_ROLE)]
    assert [item for item in window.scene.items() if item.data(BLAST_GEOMETRY_ROLE)]
    assert combined.width() > window.scene.itemsBoundingRect().width()
    window.close()
    assert app


def test_blast_window_has_project_lines_import_button(tmp_path):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from ui.prototype_2d.blast_event_window import BlastEventWindow

    app = QApplication.instance() or QApplication([])
    window = BlastEventWindow(storage_path=tmp_path / "empty.json")
    assert window.import_dataset_button.text() == "Загрузить проектные линии"
    label = window._detail_value_label("очень длинное исходное значение.csv")
    assert label.wordWrap()
    assert label.toolTip() == label.text()
    assert label.sizePolicy().horizontalPolicy().name == "Expanding"
    window.close()
    assert app


def test_blast_details_source_declares_responsive_labels():
    source = __import__('pathlib').Path('ui/prototype_2d/blast_event_window.py').read_text(encoding='utf-8')
    assert "setWordWrap(True)" in source
    assert "setToolTip(value)" in source
    assert "QScrollArea" in source
    assert "ScrollBarAlwaysOff" in source


def test_assessment_mode_does_not_render_blast_events_without_explicit_link_highlight(tmp_path):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from ui.prototype_2d.blast_event_window import BLAST_CONTEXT_ROLE, BlastEventWindow
    app = QApplication.instance() or QApplication([])
    project = tmp_path / "project.csv"; block = tmp_path / "block.csv"; collars = tmp_path / "collars.csv"
    write_csv(project, [(0, 0, 600, "lo", 1), (10, 0, 600, "lo", 2),
                        (0, 10, 620, "hi", 1), (10, 10, 620, "hi", 2)])
    production_csv(block)
    write_csv(collars, [(2, 2, 640, "h1", 1), (2, 2, 600, "h1", 2),
                        (8, 8, 645, "h2", 1), (8, 8, 600, "h2", 2)])
    state = AssessmentDomainState(); ProjectLinesDatasetService(state).import_dataset(project)
    production = BlastEventService(state).create_event(name="Production", event_type="production", event_date=None, elevation=620, csv_path=block)
    contour = BlastEventService(state).create_event(name="Contour", event_type="contour", event_date=None, elevation=640, csv_path=collars)
    archived = BlastEventService(state).create_event(name="Archived", event_type="production", event_date=None, elevation=620, csv_path=block); archived.archive()
    window = BlastEventWindow(storage_path=save_blast_event_state(state, tmp_path / "context.json"))
    window.mode_tabs.setCurrentIndex(1); window.draw_geometry()
    context_ids = [item.data(BLAST_CONTEXT_ROLE) for item in window.scene.items() if item.data(BLAST_CONTEXT_ROLE)]
    assert context_ids == []
    window.close(); assert app


def test_assessment_drawing_enters_refinement_before_confirmation_and_cancel_is_clean(tmp_path):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from ui.prototype_2d.blast_event_window import ASSESSMENT_HANDLE_ROLE, ASSESSMENT_SELECTION_ROLE, BlastEventWindow
    app = QApplication.instance() or QApplication([])
    project = tmp_path / "project.csv"
    write_csv(project, [(0, 2, 600, "lo", 1), (10, 2, 600, "lo", 2),
                        (0, 8, 620, "hi", 1), (10, 8, 620, "hi", 2)])
    state = AssessmentDomainState(); ProjectLinesDatasetService(state).import_dataset(project)
    window = BlastEventWindow(storage_path=save_blast_event_state(state, tmp_path / "workflow.json"))
    window.mode_tabs.setCurrentIndex(1); window.start_area_drawing()
    for point in ((0, 0), (10, 0), (10, 10), (0, 10)): window._drawing_click(*point)
    window._drawing_key("enter")
    assert window.workflow_state == "REFINING" and len(window.state.assessment_areas) == 0
    assert [item for item in window.scene.items() if item.data(ASSESSMENT_SELECTION_ROLE)]
    assert len([item for item in window.scene.items() if item.data(ASSESSMENT_HANDLE_ROLE)]) == 4
    window._handle_moved(1, 9, -1)
    assert window._drawing_vertices[1] == PlanPoint(9, -1)
    window.cancel_area_drawing()
    assert window.workflow_state == "IDLE" and len(window.state.assessment_areas) == 0
    assert not [item for item in window.scene.items() if item.data(ASSESSMENT_HANDLE_ROLE)]
    window.close(); assert app


def test_saved_assessment_hides_selection_polygon_and_archived_area_cannot_edit(tmp_path):
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from prototype_2d.assessment_area_service import AssessmentAreaService
    from prototype_2d.domain import PlanPolygon
    from ui.prototype_2d.blast_event_window import ASSESSMENT_HANDLE_ROLE, ASSESSMENT_SELECTION_ROLE, BlastEventWindow
    app = QApplication.instance() or QApplication([])
    project = tmp_path / "project.csv"
    write_csv(project, [(0, 2, 600, "lo", 1), (10, 2, 600, "lo", 2),
                        (0, 8, 620, "hi", 1), (10, 8, 620, "hi", 2)])
    state = AssessmentDomainState(); ProjectLinesDatasetService(state).import_dataset(project)
    selection = PlanPolygon((PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10), PlanPoint(0, 10), PlanPoint(0, 0)))
    service = AssessmentAreaService(state)
    area = service.create_area(name="Area", assessment_date=date.today(), selection_polygon=selection,
                               selected_fragments=service.generate_candidates(selection))
    window = BlastEventWindow(storage_path=save_blast_event_state(state, tmp_path / "saved-area.json"))
    window.mode_tabs.setCurrentIndex(1); window.selected_area = window.state.assessment_areas[0]; window.draw_geometry()
    assert not [item for item in window.scene.items() if item.data(ASSESSMENT_SELECTION_ROLE)]
    area = window.selected_area; area.archive(); window.edit_area_boundaries()
    assert window.workflow_state == "IDLE"
    assert not [item for item in window.scene.items() if item.data(ASSESSMENT_HANDLE_ROLE)]
    window.close(); assert app
