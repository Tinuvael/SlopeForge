from pathlib import Path


def test_drillhole_import_and_assignment_respect_existing_read_only_state():
    card = Path("ui/pages/drillhole_dataset_widgets.py").read_text(encoding="utf-8")
    widgets = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert "self.button.setEnabled(not self.read_only)" in card
    assert "assign.setEnabled(not self.read_only)" in widgets
    assert "if self.editor.read_only" in widgets
