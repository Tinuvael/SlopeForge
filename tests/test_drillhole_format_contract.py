from pathlib import Path


def test_drillhole_file_filters_use_dxf_dm_dmx_only():
    dialog = Path("ui/dialogs/blast_event_dialog.py").read_text(encoding="utf-8")
    widgets = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    for source in (dialog, widgets):
        assert "*.dxf *.dm *.dmx" in source
        assert "*.csv" not in source
