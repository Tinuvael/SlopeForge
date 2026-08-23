from pathlib import Path


def test_design_hole_has_one_canonical_engineering_group():
    domain = Path("domain/blasting/drillholes.py").read_text(encoding="utf-8")
    service = Path("application/services/drillhole_datasets.py").read_text(encoding="utf-8")
    assert "engineering_group_id: str | None" in domain
    assert "hole.engineering_group_id = group_id" in service
    assert "hole.engineering_group_id = None" in service
