from domain.blasting.drillhole_selection import hole_ids_in_polygon, point_in_polygon
from domain.blasting.drillholes import Drillhole, DrillholePoint


def hole(hole_id, x, y):
    return Drillhole(
        hole_id,
        (DrillholePoint(x, y, 630), DrillholePoint(x, y, 620)),
    )


def test_point_in_polygon_is_boundary_inclusive():
    polygon = ((0,0),(10,0),(10,10),(0,10))
    assert point_in_polygon(5,5,polygon)
    assert point_in_polygon(0,5,polygon)
    assert point_in_polygon(10,10,polygon)
    assert not point_in_polygon(11,5,polygon)


def test_polygon_selection_uses_collar_xy_only():
    holes = (
        hole("inside", 5, 5),
        hole("edge", 10, 4),
        hole("outside", 20, 20),
    )
    selected = hole_ids_in_polygon(holes, ((0,0),(10,0),(10,10),(0,10)))
    assert selected == {"inside", "edge"}
