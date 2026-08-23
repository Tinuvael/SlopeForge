from pathlib import Path


def test_contour_creation_reuses_the_geometry_source_for_initial_design_holes():
    source = Path("application/use_cases/create_blast_event.py").read_text(encoding="utf-8")
    assert 'command.geometry_file_path\n                if command.event_type == "contour"' in source
