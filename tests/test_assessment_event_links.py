from datetime import date, datetime, timezone

import pytest

from prototype_2d.assessment_event_link_service import AssessmentEventLinkService
from prototype_2d.domain import (AssessmentArea, AssessmentAreaGeometryRevision,
    AssessmentDomainState, BlastEvent, PlanMultiPoint, PlanPoint, PlanPolygon)
from prototype_2d.geometry import (points_from_multipoint_inside_polygon,
    polygon_intersects_polygon)


def polygon(*coordinates):
    points = tuple(PlanPoint(*xy) for xy in coordinates)
    return PlanPolygon(points + (points[0],))


def area(selection=None):
    selection = selection or polygon((0, 0), (10, 0), (10, 10), (0, 10))
    revision = AssessmentAreaGeometryRevision("AA-1-R001", "AA-1", 1,
        datetime(2026, 1, 1, tzinfo=timezone.utc), "D-1", selection, selection,
        600, 630, ())
    return AssessmentArea("AA-1", "Area", date(2026, 1, 1), [revision], revision.id)


def event(event_id, elevation, geometry, event_type="production"):
    value = BlastEvent(event_id, event_id, event_type, None, elevation)
    value.add_geometry_revision(source_file_name="x.csv", source_geometry=[],
                                plan_geometry=geometry, elevation=elevation)
    return value


@pytest.mark.parametrize("elevation,expected", [(600, 0), (610, 1), (630, 1), (631, 0)])
def test_elevation_interval_is_lower_exclusive_upper_inclusive(elevation, expected):
    assessment = area(); blast = event("BE-1", elevation, polygon((2, 2), (4, 2), (4, 4), (2, 4)))
    assert len(AssessmentEventLinkService(AssessmentDomainState(blast_events=[blast])).find_candidates(assessment)) == expected


def test_polygon_intersection_crossing_containment_touch_and_disjoint():
    box = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    assert polygon_intersects_polygon(box, polygon((5, -2), (7, -2), (7, 12), (5, 12)))
    assert polygon_intersects_polygon(box, polygon((2, 2), (3, 2), (3, 3), (2, 3)))
    assert polygon_intersects_polygon(polygon((2, 2), (3, 2), (3, 3), (2, 3)), box)
    assert polygon_intersects_polygon(box, polygon((10, 2), (12, 2), (12, 4), (10, 4)))
    assert not polygon_intersects_polygon(box, polygon((20, 20), (21, 20), (21, 21), (20, 21)))


def test_contour_freezes_only_copied_matching_collars_including_boundary():
    multipoint = PlanMultiPoint((PlanPoint(5, 5), PlanPoint(0, 4), PlanPoint(20, 20)))
    matched = points_from_multipoint_inside_polygon(multipoint, area().selection_polygon_frozen)
    assert matched == (PlanPoint(5, 5), PlanPoint(0, 4))
    assessment = area(); blast = event("BE-C", 610, multipoint, "contour")
    link = AssessmentEventLinkService(AssessmentDomainState(blast_events=[blast])).refresh_suggestions(assessment)
    assert link.contour_candidates == 1
    assert assessment.event_links[0].frozen_intersection_geometry.points == matched
    assert assessment.event_links[0].frozen_intersection_geometry.points[0] is not multipoint.points[0]


def test_refresh_is_revision_safe_preserves_decisions_and_replaces_suggestion():
    assessment = area(); blast = event("BE-1", 610, polygon((2, 2), (4, 2), (4, 4), (2, 4)))
    service = AssessmentEventLinkService(AssessmentDomainState(blast_events=[blast]))
    service.refresh_suggestions(assessment); old = assessment.event_links[0]
    assert old.assessment_area_geometry_revision_id == assessment.active_geometry_revision_id
    service.confirm_link(assessment, old.id); old_revision = old.geometry_revision_id
    blast.add_geometry_revision(source_file_name="new.csv", source_geometry=[], plan_geometry=blast.active_geometry_revision().plan_geometry, elevation=610)
    service.refresh_suggestions(assessment)
    assert old in assessment.event_links and old.geometry_revision_id == old_revision and service.is_stale(old)


def test_manual_outside_criteria_duplicate_archive_guards():
    assessment = area(); blast = event("BE-1", 999, polygon((20, 20), (21, 20), (21, 21), (20, 21)))
    service = AssessmentEventLinkService(AssessmentDomainState(blast_events=[blast]))
    link = service.add_manual_link(assessment, blast.id)
    assert (link.status, link.source) == ("confirmed", "manual")
    with pytest.raises(ValueError): service.add_manual_link(assessment, blast.id)
    assessment.archive()
    with pytest.raises(ValueError): service.exclude_link(assessment, link.id)
