from pathlib import Path


def test_drillhole_import_does_not_restore_csv_geometry_path():
    service = Path("application/services/drillhole_datasets.py").read_text(encoding="utf-8")
    dialog = Path("ui/dialogs/blast_event_dialog.py").read_text(encoding="utf-8")
    assert ".csv" not in service.lower()
    assert "*.csv" not in dialog
