"""Pure validation for the complete Assessment aggregate.

This module deliberately knows nothing about SQLAlchemy sessions, Qt, or files.
"""
from __future__ import annotations

import math
from pathlib import PurePath

from prototype_2d.domain import AssessmentDomainState


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
    if sum(bool(x.is_active) for x in state.datasets) > 1:
        _fail("at most one dataset may be active")
    event_ids = _ids(state.blast_events, "blast event")
    event_revisions: dict[str, str] = {}
    for event in state.blast_events:
        if not math.isfinite(event.elevation):
            _fail("blast event elevation must be finite")
        revisions = _revisions(event.geometry_revisions, event.id, "blast_event_id", "blast geometry revision")
        if event.active_geometry_revision_id is not None and event.active_geometry_revision_id not in revisions:
            _fail(f"active geometry revision does not exist for event {event.id!r}")
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
            if revision.source_dataset_id not in dataset_ids:
                _fail(f"source dataset {revision.source_dataset_id!r} does not exist")
            if not all(math.isfinite(x) for x in (revision.lower_elevation, revision.upper_elevation)):
                _fail("area elevations must be finite")
            if revision.lower_elevation >= revision.upper_elevation:
                _fail("lower elevation must be below upper elevation")
            for item in revision.horizon_slices:
                if not item.id.strip() or not math.isfinite(item.elevation):
                    _fail("horizon slice IDs and elevations must be persistable")
        _ids(area.event_links, "assessment event link")
        for link in area.event_links:
            if link.assessment_area_geometry_revision_id not in revisions:
                _fail("link references a geometry revision outside its Assessment Area")
            if link.blast_event_id not in event_ids or event_revisions.get(link.geometry_revision_id) != link.blast_event_id:
                _fail("link references an invalid BlastEvent geometry revision")
    card_ids = _ids(state.technical_cards, "technical card")
    for card in state.technical_cards:
        if card.blast_event_id not in event_ids:
            _fail("technical card references a missing BlastEvent")
        revisions = _revisions(card.revisions, card.id, "technical_card_id", "technical-card revision")
        if card.active_revision_id is not None and card.active_revision_id not in revisions:
            _fail("technical-card active revision does not exist")
        for revision in card.revisions:
            if event_revisions.get(revision.geometry_revision_id) != card.blast_event_id:
                _fail("technical-card geometry belongs to another event")
    evaluation_ids = _ids(state.evaluations, "evaluation")
    for evaluation in state.evaluations:
        if evaluation.assessment_area_id not in area_ids:
            _fail("evaluation references a missing Assessment Area")
        revisions = _revisions(evaluation.revisions, evaluation.id, "evaluation_id", "evaluation revision")
        if evaluation.active_revision_id is not None and evaluation.active_revision_id not in revisions:
            _fail("evaluation active revision does not exist")
        for revision in evaluation.revisions:
            if area_revisions.get(revision.assessment_area_geometry_revision_id) != evaluation.assessment_area_id:
                _fail("evaluation geometry belongs to another Assessment Area")
    del card_ids
    _ids(state.attachments, "attachment")
    for attachment in state.attachments:
        owners = event_ids if attachment.owner_type == "blast_event" else evaluation_ids
        if attachment.owner_id not in owners:
            _fail("attachment owner does not exist")
        path = PurePath(attachment.relative_path)
        if path.is_absolute() or not attachment.relative_path.strip():
            _fail("attachment path must be relative")
        if attachment.file_size_bytes < 0:
            _fail("attachment size must be non-negative")
