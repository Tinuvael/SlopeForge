from pathlib import Path


def test_drillhole_feature_is_embedded_in_existing_blast_pages():
    block = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    contour = Path("ui/pages/contour_event_page.py").read_text(encoding="utf-8")
    widgets = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert "TechnicalCardEditorWidget" in block
    assert "TechnicalCardEditorWidget" in contour
    assert "DrillholeDatasetCard" in widgets
    assert not Path("ui/pages/drillhole_workspace.py").exists()
