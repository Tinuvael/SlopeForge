from pathlib import Path


def test_drillhole_source_files_live_in_blast_event_file_storage():
    storage = Path("infrastructure/files/drillhole_geometry.py").read_text(encoding="utf-8")
    model = Path("database/drillhole_models.py").read_text(encoding="utf-8")
    assert '"blast_events"' in storage and '"drillholes"' in storage
    assert "source_files_json" in model
    assert "LargeBinary" not in model
