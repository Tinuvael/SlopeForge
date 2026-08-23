from pathlib import Path


def test_assigning_hole_to_new_group_moves_it_from_previous_group():
    source = Path("application/services/drillhole_datasets.py").read_text(encoding="utf-8")
    assert "if hole.hole_id in selected:" in source
    assert "hole.engineering_group_id = group_id" in source
    assert "elif hole.engineering_group_id == group_id:" in source
