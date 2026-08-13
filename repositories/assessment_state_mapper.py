"""Pure validation for the complete Assessment aggregate.

This module deliberately knows nothing about SQLAlchemy sessions, Qt, or files.
"""
from __future__ import annotations

import math
from pathlib import PurePath

from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.geometry import ProjectLineSpan, StraightConnector


class AssessmentPersistenceError(Exception):
    """Base class for Assessment persistence failures."""


class AssessmentSiteNotFoundError(AssessmentPersistenceError):
    pass


class AssessmentStateValidationError(AssessmentPersistenceError, ValueError):
    pass


class AssessmentPersistenceCorruptionError(AssessmentPersistenceError):
    pass


def _fail(message: str) -> None:
    raise AssessmentStateValidationError(message)


def _ids(items, label: str) -> set[str]:
    result: set[str] = set()
    for item in items:
        value = getattr(item, "id", None)
        if not isinstance(value, str) or not value.strip():
            _fail(f"{label}: stable ID must be a non-empty string")
        if value in result:
            _fail(f"{label}: duplicate ID {value!r}")
        result.add(value)
    return result


def _revisions(items, parent_id: str, parent_attr: str, label: str) -> set[str]:
    ids = _ids(items, label)
    numbers: set[int] = set()
    for revision in items:
        if getattr(revision, parent_attr) != parent_id:
            _fail(f"{label} {revision.id!r} has the wrong parent")
        number = revision.revision_number
        if number <= 0 or number in numbers:
            _fail(f"{label}: revision numbers must be positive and unique per parent")
        numbers.add(number)
    return ids


def validate_assessment_state(state: AssessmentDomainState) -> None:
    """Validate only invariants needed for a lossless database round trip."""
    if not isinstance(state, AssessmentDomainState):
        _fail("state must be AssessmentDomainState")
    dataset_ids = _ids(state.datasets, "dataset")
    datasets_by_id = {item.id: item for item in state.datasets}
    if sum(bool(x.is_active) for x in state.datasets) > 1:
        _fail("at most one dataset may be active")
    event_ids = _ids(state.blast_events, "blast event")
    events_by_id = {item.id: item for item in state.blast_events}
    event_revisions: dict[str, str] = {}
    for event in state.blast_events:
        if not math.isfinite(event.elevation):
            _fail("blast event elevation must be finite")
        revisions = _revisions(event.geometry_revisions, event.id, "blast_event_id", "blast geometry revision")
        if event.active_geometry_revision_id is not None and event.active_geometry_revision_id not in revisions:
            _fail(f"active geometry revision does not exist for event {event.id!r}")
        marked_active = [item.id for item in event.geometry_revisions if item.is_active]
        if len(marked_active) > 1:
            _fail(f"BlastEvent {event.id!r} has multiple active geometry revisions")
        expected_active = marked_active[0] if marked_active else None
        if event.active_geometry_revision_id != expected_active:
            _fail(f"BlastEvent {event.id!r} active revision ID disagrees with is_active flags")
        for revision in event.geometry_revisions:
            if not math.isfinite(revision.elevation):
                _fail("blast geometry elevation must be finite")
            if revision.id in event_revisions:
                _fail(f"duplicate blast geometry revision ID {revision.id!r}")
            event_revisions[revision.id] = event.id
    area_ids = _ids(state.assessment_areas, "assessment area")
    area_revisions: dict[str, str] = {}
    for area in state.assessment_areas:
        revisions = _revisions(area.geometry_revisions, area.id, "assessment_area_id", "area geometry revision")
        if area.active_geometry_revision_id is not None and area.active_geometry_revision_id not in revisions:
            _fail(f"active geometry revision does not exist for area {area.id!r}")
        for revision in area.geometry_revisions:
            if revision.id in area_revisions:
                _fail(f"duplicate area geometry revision ID {revision.id!r}")
            area_revisions[revision.id] = area.id
            for elevation in (revision.min_elevation, revision.max_elevation):
                if elevation is not None and not math.isfinite(elevation):
                    _fail("area elevation summary must be finite")
            for segment in revision.boundary.segments:
                anchors = ((segment.start_anchor, segment.end_anchor) if isinstance(segment, ProjectLineSpan)
                           else (segment.start_anchor, segment.end_anchor) if isinstance(segment, StraightConnector)
                           else ())
                for anchor in (item for item in anchors if item is not None):
                    dataset = datasets_by_id.get(anchor.source_dataset_id)
                    if dataset is None:
                        _fail(f"boundary anchor references missing dataset {anchor.source_dataset_id!r}")
                    line = next((item for item in dataset.lines if item.source_id == anchor.source_line_id), None)
                    if line is None:
                        _fail(f"boundary anchor references missing Project Line {anchor.source_line_id!r}")
                    if anchor.source_segment_index >= len(line.points)-1:
                        _fail("boundary anchor source segment index is outside the historical Project Line")
        _ids(area.event_links, "assessment event link")
        link_identities: set[tuple[str, str, str]] = set()
        for link in area.event_links:
            if link.assessment_area_geometry_revision_id not in revisions:
                _fail("link references a geometry revision outside its Assessment Area")
            if link.blast_event_id not in event_ids or event_revisions.get(link.geometry_revision_id) != link.blast_event_id:
                _fail("link references an invalid BlastEvent geometry revision")
            identity = (link.assessment_area_geometry_revision_id, link.geometry_revision_id, link.source)
            if identity in link_identities:
                _fail("duplicate AssessmentEventLink geometry/source identity")
            link_identities.add(identity)
            if link.created_at is None:
                _fail(f"AssessmentEventLink {link.id!r} has no created_at")
    card_ids = _ids(state.technical_cards, "technical card")
    card_event_ids: set[str] = set()
    for card in state.technical_cards:
        if card.blast_event_id not in event_ids:
            _fail("technical card references a missing BlastEvent")
        if card.blast_event_id in card_event_ids:
            _fail(f"BlastEvent {card.blast_event_id!r} has more than one technical card")
        card_event_ids.add(card.blast_event_id)
        revisions = _revisions(card.revisions, card.id, "technical_card_id", "technical-card revision")
        if card.active_revision_id is not None and card.active_revision_id not in revisions:
            _fail("technical-card active revision does not exist")
        for revision in card.revisions:
            if event_revisions.get(revision.geometry_revision_id) != card.blast_event_id:
                _fail("technical-card geometry belongs to another event")
            if revision.event_type != events_by_id[card.blast_event_id].event_type:
                _fail("technical-card revision event_type differs from its BlastEvent")
    evaluation_ids = _ids(state.evaluations, "evaluation")
    evaluation_area_ids: set[str] = set()
    for evaluation in state.evaluations:
        if evaluation.assessment_area_id not in area_ids:
            _fail("evaluation references a missing Assessment Area")
        if evaluation.assessment_area_id in evaluation_area_ids:
            _fail(f"Assessment Area {evaluation.assessment_area_id!r} has more than one evaluation")
        evaluation_area_ids.add(evaluation.assessment_area_id)
        revisions = _revisions(evaluation.revisions, evaluation.id, "evaluation_id", "evaluation revision")
        if evaluation.active_revision_id is not None and evaluation.active_revision_id not in revisions:
            _fail("evaluation active revision does not exist")
        for revision in evaluation.revisions:
            if area_revisions.get(revision.assessment_area_geometry_revision_id) != evaluation.assessment_area_id:
                _fail("evaluation geometry belongs to another Assessment Area")
    del card_ids
    _ids(state.attachments, "attachment")
    for attachment in state.attachments:
        if attachment.owner_type not in {"blast_event", "assessment_evaluation"}:
            _fail(f"unsupported attachment owner_type {attachment.owner_type!r}")
        owners = event_ids if attachment.owner_type == "blast_event" else evaluation_ids
        if attachment.owner_id not in owners:
            _fail("attachment owner does not exist")
        path = PurePath(attachment.relative_path)
        if path.is_absolute() or not attachment.relative_path.strip():
            _fail("attachment path must be relative")
        if attachment.file_size_bytes < 0:
            _fail("attachment size must be non-negative")
