from pathlib import Path


def test_no_nearest_neighbor_production_pattern_inference_is_introduced():
    files = (
        "domain/blasting/drillholes.py",
        "application/services/drillhole_datasets.py",
        "ui/pages/technical_card_widgets.py",
    )
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files).lower()
    assert "nearest_neighbor" not in text
    assert "nearest-neighbour average" not in text
