from pathlib import Path


def test_create_command_keeps_block_geometry_separate_from_design_drillholes():
    source = Path("application/use_cases/create_blast_event.py").read_text(encoding="utf-8")
    assert "geometry_file_path: str" in source
    assert "design_drillhole_file_path: str | None = None" in source
