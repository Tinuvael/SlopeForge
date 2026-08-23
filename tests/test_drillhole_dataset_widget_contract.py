from pathlib import Path


def test_actual_dataset_summary_surfaces_low_confidence_matches():
    source = Path("ui/pages/drillhole_dataset_widgets.py").read_text(encoding="utf-8")
    assert '"matched_geometry_low_confidence"' in source
    assert '"Low-confidence matches"' in source
