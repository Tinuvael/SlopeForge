import pytest

from domain.blasting.contour_drilling import order_contour_holes, summarize_contour_drilling
from domain.blasting.drillholes import Drillhole, DrillholePoint


def hole(hole_id, x, y, *, collar_z=630, toe_z=620):
    return Drillhole(
        hole_id,
        (DrillholePoint(x, y, collar_z), DrillholePoint(x, y, toe_z)),
    )


def test_straight_contour_is_ordered_by_geometry_not_input_order():
    holes = (hole("C", 10, 0), hole("A", 0, 0), hole("B", 5, 0))

    ordered = order_contour_holes(holes)
    summary = summarize_contour_drilling(holes)

    assert [item.hole_id for item in ordered] in (["A", "B", "C"], ["C", "B", "A"])
    assert summary.line_length_m == pytest.approx(10)
    assert summary.mean_spacing_m == pytest.approx(5)
    assert summary.median_spacing_m == pytest.approx(5)
    assert summary.min_spacing_m == pytest.approx(5)
    assert summary.max_spacing_m == pytest.approx(5)
    assert summary.alignment_azimuth_deg in pytest.approx((90.0, 270.0))


def test_curved_contour_uses_local_chain_length_for_spacing():
    holes = (
        hole("H-3", 10, 10),
        hole("H-1", 0, 0),
        hole("H-2", 10, 0),
    )

    summary = summarize_contour_drilling(holes)

    assert summary.line_length_m == pytest.approx(20)
    assert summary.mean_spacing_m == pytest.approx(10)
    assert summary.ordered_hole_ids[1] == "H-2"
