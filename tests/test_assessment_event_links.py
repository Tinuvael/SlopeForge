from datetime import date, datetime, timezone

import pytest

from prototype_2d.assessment_event_link_service import AssessmentEventLinkService
from prototype_2d.blast_event_service import BlastEventService
from domain.geometry.types import PlanMultiPoint, PlanPoint, PlanPolygon
from domain.blasting.entities import BlastEvent
from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision
from application.state.assessment_domain_state import AssessmentDomainState
from domain.geometry.operations import (points_from_multipoint_inside_polygon,
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


def event(event_id, elevation, geometry, event_type="production", name=None, source="x.csv"):
    value = BlastEvent(event_id, name or event_id, event_type, None, elevation)
    value.add_geometry_revision(source_file_name=source, source_geometry=[],
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


def matching_events(production=0, contour=0):
    events = [event(f"BE-P-{index:03}", 610, polygon((1, 1), (4, 1), (4, 4), (1, 4)),
                    name="Одинаковое имя", source="same.csv") for index in range(production)]
    events += [event(f"BE-C-{index:03}", 610, PlanMultiPoint((PlanPoint(2, 2), PlanPoint(20, 20))),
                     "contour", name="Одинаковое имя", source="same.csv") for index in range(contour)]
    return events


@pytest.mark.parametrize("production,contour", [(10, 0), (0, 6), (10, 6)])
def test_all_distinct_event_ids_link_even_with_same_elevation_name_and_csv(production, contour):
    assessment = area(); events = matching_events(production, contour)
    result = AssessmentEventLinkService(AssessmentDomainState(blast_events=events)).refresh_suggestions(assessment)
    assert (result.production_matches, result.contour_matches) == (production, contour)
    assert len(assessment.links_for_revision()) == production + contour
    assert len({link.blast_event_id for link in assessment.links_for_revision()}) == production + contour


def test_combined_scan_links_exactly_sixteen_and_reports_rejections():
    events = matching_events(10, 6)
    events += [event(f"HIGH-{i}", 700, polygon((1, 1), (2, 1), (2, 2), (1, 2))) for i in range(3)]
    events += [event(f"OUT-{i}", 610, polygon((20, 20), (22, 20), (22, 22), (20, 22))) for i in range(2)]
    archived = event("ARCHIVED", 610, polygon((1, 1), (2, 1), (2, 2), (1, 2))); archived.archive(); events.append(archived)
    assessment = area(); result = AssessmentEventLinkService(AssessmentDomainState(blast_events=events)).refresh_suggestions(assessment)
    assert len(assessment.links_for_revision()) == 16
    assert (result.events_rejected_by_elevation, result.events_rejected_by_spatial_match) == (3, 2)
    assert result.active_events_scanned == 21 and result.total_links_for_active_area_revision == 16


def test_repeated_refresh_and_individual_decisions_never_hide_other_events():
    assessment = area(); service = AssessmentEventLinkService(AssessmentDomainState(blast_events=matching_events(10, 6)))
    service.refresh_suggestions(assessment)
    service.confirm_link(assessment, assessment.event_links[0].id)
    service.exclude_link(assessment, assessment.event_links[1].id)
    result = service.refresh_suggestions(assessment)
    assert len(assessment.links_for_revision()) == 16
    assert len({(link.assessment_area_geometry_revision_id, link.blast_event_id)
                for link in assessment.links_for_revision()}) == 16
    assert result.protected_existing_links == 2 and result.suggestions_added == 14


def test_hundred_events_and_json_round_trip_preserve_every_link():
    assessment = area(); state = AssessmentDomainState(blast_events=matching_events(75, 25), assessment_areas=[assessment])
    AssessmentEventLinkService(state).refresh_suggestions(assessment)
    restored = AssessmentDomainState.from_dict(state.to_dict())
    links = restored.assessment_areas[0].links_for_revision()
    assert len(links) == 100 and len({link.blast_event_id for link in links}) == 100


def test_linking_is_independent_of_visual_layer_state():
    events = matching_events(10, 6)
    ids_by_visual_state = []
    for blast_layers_visible in (True, False):
        # The flag deliberately belongs to the presentation scenario and is never passed
        # to the pure service: visible QGraphics layers cannot affect domain matching.
        assert isinstance(blast_layers_visible, bool)
        assessment = area(); service = AssessmentEventLinkService(AssessmentDomainState(blast_events=events))
        service.refresh_suggestions(assessment)
        ids_by_visual_state.append({link.blast_event_id for link in assessment.links_for_revision()})
    assert ids_by_visual_state[0] == ids_by_visual_state[1]


def test_multiple_auto_suggested_event_elevations_link_to_same_area(tmp_path):
    state = AssessmentDomainState(); import_service = BlastEventService(state)
    for index, elevation in enumerate((610, 620, 630)):
        source = tmp_path / f"block-{index}.csv"
        source.write_text("XP,YP,ZP,SID,PTN\n" + "\n".join(
            f"{x},{y},{elevation},top,{number}" for number, (x, y) in enumerate(
                ((1, 1), (4, 1), (4, 4), (1, 1)), 1)), encoding="utf-8")
        preview = import_service.inspect_event_geometry("production", source)
        import_service.create_event(name=f"Block {index}", event_type="production", event_date=None,
                                    elevation=preview.suggested_elevation, csv_path=source)
    assessment = area(); AssessmentEventLinkService(state).refresh_suggestions(assessment)
    assert len(assessment.links_for_revision()) == 3
