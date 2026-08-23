from pathlib import Path


def test_matching_uses_explicit_high_low_and_unmatched_states():
    source = Path("domain/blasting/drillholes.py").read_text(encoding="utf-8")
    for state in (
        "matched_by_id",
        "matched_geometry_high_confidence",
        "matched_geometry_low_confidence",
        "unmatched_design",
        "unmatched_actual",
    ):
        assert state in source
    assert "matched_nearest_collar" not in source
