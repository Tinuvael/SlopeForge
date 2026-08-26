import pytest

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.wall_conformance import WallAlignmentSample, intersect_surface_with_profile


def test_profile_half_width_clips_one_segment_at_both_limits() -> None:
    surface = TriangleSurface(
        vertices=(
            SurfaceVertex(-10, -1, 0),
            SurfaceVertex(10, -1, 20),
            SurfaceVertex(0, 1, 10),
        ),
        triangles=(SurfaceTriangle((0, 1, 2), source_id="wide"),),
    )
    alignment = WallAlignmentSample(
        chainage_m=0,
        origin=SurfaceVertex(0, 0, 10),
        tangent_xy=(0.0, 1.0),
        normal_xy=(1.0, 0.0),
    )

    segments = intersect_surface_with_profile(
        surface,
        alignment,
        half_width_m=2.0,
    )

    assert len(segments) == 1
    assert segments[0].start.u == pytest.approx(-2.0)
    assert segments[0].start.z == pytest.approx(8.0)
    assert segments[0].end.u == pytest.approx(2.0)
    assert segments[0].end.z == pytest.approx(12.0)
