from pathlib import Path


def test_all_active_line_geometry_pickers_offer_dxf_dm_and_dmx_only():
    root = Path(__file__).parents[1]
    picker_files = [
        "ui/project_dialog.py", "ui/pages/dashboards/site_dashboard.py",
        "ui/pages/dashboards/domain_dashboard.py",
        "ui/dialogs/blast_event_dialog.py", "ui/pages/block_page.py",
        "ui/pages/contour_event_page.py",
    ]
    for relative in picker_files:
        source = (root / relative).read_text(encoding="utf-8")
        assert "*.dxf *.dm *.dmx" in source, relative
        assert "*.csv *.dxf" not in source, relative
        assert "Datamine CSV" not in source, relative
    dialog = (root / "ui/dialogs/blast_event_dialog.py").read_text(encoding="utf-8")
    assert 'QPushButton(tr("Select CSV"))' not in dialog
    catalogue = (root / "translations/slopeforge_ru.ts").read_text(encoding="utf-8")
    assert "Выбрать файл геометрии" in catalogue and "Файл геометрии *" in catalogue


def test_retired_csv_line_import_code_is_absent():
    root = Path(__file__).parents[1]
    retired = (
        "infrastructure/geometry_import/csv.py",
        "ui/dialogs/geometry_import_dialogs.py",
        "tests/test_datamine_csv_importer.py",
        "tests/fixtures/datamine_lines_sample.csv",
        "tests/fixtures/contour_drillholes_with_markers.csv",
        "tests/fixtures/production_two_closed_levels.csv",
        "tests/fixtures/project_lines_separated_parts.csv",
    )
    assert [relative for relative in retired if (root / relative).exists()] == []
