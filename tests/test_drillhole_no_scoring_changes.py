from pathlib import Path


def test_drillhole_feature_does_not_touch_dai_fci_scoring():
    files = (
        "application/services/drillhole_datasets.py",
        "domain/blasting/drillholes.py",
        "ui/pages/technical_card_widgets.py",
    )
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files).lower()
    assert "dai" not in text
    assert "fci" not in text
