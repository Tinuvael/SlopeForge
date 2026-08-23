from pathlib import Path


def test_contour_design_refresh_derives_metrics_without_writing_dataset_assignment():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("    def _apply_contour_design")
    end = source.index("    @staticmethod\n    def _deviation_values", start)
    method = source[start:end]
    assert "effective_holes" in method
    assert "assign_design_holes" not in method
    assert "assigned_holes" not in method
