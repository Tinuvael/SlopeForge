from pathlib import Path


def test_production_create_dialog_exposes_optional_design_drillholes():
    source = Path("ui/dialogs/blast_event_dialog.py").read_text(encoding="utf-8")
    assert 'tr("Design drillholes")' in source
    assert '"design_drillhole_path"' in source
    assert "self.geometry_form.setRowVisible(self.design_drillholes_host, is_production)" in source


def test_main_window_forwards_optional_design_drillholes_to_create_command():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")
    assert 'design_drillhole_file_path=values.get("design_drillhole_path")' in source


def test_opening_contour_design_does_not_persist_group_assignment_implicitly():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("    def _apply_contour_design")
    end = source.index("    @staticmethod\n    def _deviation_values", start)
    method = source[start:end]
    assert "assign_design_holes(" not in method
    assert "assigned_holes(" not in method
