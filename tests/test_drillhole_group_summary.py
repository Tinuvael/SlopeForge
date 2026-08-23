from pathlib import Path


def test_production_group_sync_does_not_infer_burden_spacing_or_rows_from_nearest_neighbours():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("    def _apply_design_group_metrics")
    end = source.index("    def _primary_contour_group", start)
    method = source[start:end]
    assert "group.hole_count = summary.hole_count" in method
    assert "group.average_depth_m = summary.mean_length_m" in method
    assert "group.inclination_deg = summary.mean_inclination_deg" in method
    assert "group.burden_m =" not in method
    assert "group.row_count =" not in method
    assert "group.spacing_m =" in method  # contour-only branch
