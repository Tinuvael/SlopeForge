from pathlib import Path


def test_all_active_geometry_pickers_offer_csv_and_dxf():
    root = Path(__file__).parents[1]
    picker_files = [
        "ui/project_dialog.py", "ui/pages/dashboards/site_dashboard.py",
        "ui/widgets/assessment_workspace.py", "ui/pages/block_page.py",
        "ui/pages/contour_event_page.py",
    ]
    for relative in picker_files:
        source = (root / relative).read_text(encoding="utf-8")
        assert "*.csv *.dxf" in source, relative
    workspace = (root / "ui/widgets/assessment_workspace.py").read_text(encoding="utf-8")
    assert 'QPushButton(tr("Select CSV"))' not in workspace
    catalogue = (root / "translations/slopeforge_ru.ts").read_text(encoding="utf-8")
    assert "Выбрать файл геометрии" in catalogue and "Файл геометрии *" in catalogue
