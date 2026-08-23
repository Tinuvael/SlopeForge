from domain.blasting.drillholes import Drillhole, DrillholePoint, match_actual_to_design


def hole(hole_id, x, y, toe_x=None, toe_y=None):
    return Drillhole(
        hole_id,
        (
            DrillholePoint(x, y, 630),
            DrillholePoint(x if toe_x is None else toe_x, y if toe_y is None else toe_y, 620),
        ),
    )


def test_stable_compatible_ids_remain_preferred():
    design = (hole("H-1", 0, 0), hole("H-2", 10, 0))
    actual = (hole("H-1", 0.3, 0), hole("A-2", 10.2, 0))
    matches = match_actual_to_design(design, actual)
    by_actual = {item.actual_hole_id: item for item in matches if item.actual_hole_id}
    assert by_actual["H-1"].match_method == "matched_by_id"
    assert by_actual["A-2"].match_method == "matched_geometry_high_confidence"


def test_dense_geometric_match_is_flagged_low_confidence():
    design = (hole("D-1", 0, 0), hole("D-2", 1, 0))
    actual = (hole("A-1", 0.49, 0),)
    match = next(item for item in match_actual_to_design(design, actual) if item.actual_hole_id)
    assert match.match_method == "matched_geometry_low_confidence"


def test_isolated_geometric_match_is_high_confidence():
    design = (hole("D-1", 0, 0), hole("D-2", 20, 0))
    actual = (hole("A-1", 0.5, 0),)
    match = next(item for item in match_actual_to_design(design, actual) if item.actual_hole_id)
    assert match.match_method == "matched_geometry_high_confidence"
