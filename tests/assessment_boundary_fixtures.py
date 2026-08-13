"""Canonical #80 Assessment geometry builders shared by tests."""
from domain.assessment.entities import AssessmentAreaGeometryRevision
from domain.assessment.geometry import (AssessmentBoundary, ProjectLineAnchor, ProjectLineSpan,
    SpatialPoint, StraightConnector, derive_elevation_summary, derive_plan_polygon)


def boundary_from_polygon(polygon, *, dataset_id="D-1", line_id="L1", minimum=100.0, maximum=110.0):
    vertices = polygon.ring[:-1]
    points = [SpatialPoint(p.x, p.y, minimum if i == 0 else maximum if i == 1 else None)
              for i, p in enumerate(vertices)]
    start = ProjectLineAnchor(dataset_id, line_id, 0, 0.0, points[0])
    end = ProjectLineAnchor(dataset_id, line_id, 0, 1.0, points[1])
    segments = [ProjectLineSpan(start, end, (points[0], points[1]))]
    for index in range(1, len(points)):
        next_index = (index + 1) % len(points)
        segments.append(StraightConnector(points[index], points[next_index],
            end if index == 1 else None, start if next_index == 0 else None))
    return AssessmentBoundary(tuple(segments))


def geometry_revision(identifier, area_id, number, created_at, polygon, *, dataset_id="D-1",
                      line_id="L1", minimum=100.0, maximum=110.0, change_reason=None):
    boundary = boundary_from_polygon(polygon, dataset_id=dataset_id, line_id=line_id,
                                     minimum=minimum, maximum=maximum)
    return AssessmentAreaGeometryRevision(identifier, area_id, number, created_at, boundary,
        derive_plan_polygon(boundary), *derive_elevation_summary(boundary), change_reason)
