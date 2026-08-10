"""Database-independent contract tests for Assessment persistence validation."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import importlib
import math
import subprocess
import sys

import pytest

from domain.geometry.types import PlanLineString, PlanPoint, PlanPolygon
from prototype_2d.domain import AssessmentArea, AssessmentAreaGeometryRevision, AssessmentDomainState, AssessmentEventLink, AssessmentHorizonSlice, BlastEvent, EntityAttachment, ProjectLinesDataset
from domain.geometry.types import DatamineLine, DataminePoint
from prototype_2d.technical_card import BlastEventTechnicalCard, new_technical_card
from prototype_2d.wall_assessment import AssessmentAreaEvaluation, AssessmentAreaEvaluationService
from repositories.assessment_state_mapper import AssessmentStateValidationError, validate_assessment_state

NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)


def line(identifier="L1", z=100.0):
    return DatamineLine(identifier, [DataminePoint(0, 0, z, 1), DataminePoint(10, 0, z, 2)])


def polygon(offset=0.0):
    points = tuple(PlanPoint(x + offset, y) for x, y in ((0, 0), (10, 0), (10, 10), (0, 0)))
    return PlanPolygon(points)


def event(identifier, event_type, elevation):
    value = BlastEvent(identifier, identifier, event_type, date(2026, 8, 4), elevation)
    for number in (1, 2):
        revision = value.add_geometry_revision(source_file_name=f"{identifier}-{number}.csv",
            source_geometry=[line(f"{identifier}-L{number}", elevation)],
            plan_geometry=polygon(number), elevation=elevation, imported_at=NOW)
        revision.id = f"{identifier}-R{number}"
        revision.revision_number = number
    value.active_geometry_revision_id = value.geometry_revisions[-1].id
    return value


def build_rich_state():
    datasets = [ProjectLinesDataset("D1", "old", NOW, "old.csv", False, [line()]),
                ProjectLinesDataset("D2", "active", NOW, "active.csv", True, [line("L2", 110)])]
    production, contour = event("BE-P", "production", 100), event("BE-C", "contour", 110)
    revisions = [AssessmentAreaGeometryRevision(
        f"AA-R{number}", "AA", number, NOW, "D2", polygon(number), polygon(number + .5),
        90 + number, 120 + number,
        (AssessmentHorizonSlice(f"HS-{number}", "L2", 100 + number, "internal_horizon",
            PlanLineString((PlanPoint(0, number), PlanPoint(10, number)))),), None if number == 2 else "initial")
        for number in (1, 2)]
    area = AssessmentArea("AA", "Area", date(2026, 8, 4), revisions, "AA-R2", [
        AssessmentEventLink("BE-P", "BE-P-R1", "confirmed", "manual", polygon(), "LINK-OLD", "AA-R1", NOW),
        AssessmentEventLink("BE-C", "BE-C-R2", "confirmed", "automatic", polygon(1), "LINK-ACTIVE", "AA-R2", NOW),
    ])
    card, draft = new_technical_card(production)
    draft.id = ""; card.id = "TC-P"; draft.technical_card_id = card.id
    card.save_revision(draft, change_reason="first")
    card.save_revision(deepcopy(card.active_revision()), status="draft", change_reason="second")
    evaluation, draft_evaluation = AssessmentAreaEvaluationService(
        AssessmentDomainState(datasets, [production, contour], [area], [card])).new_evaluation(area)
    evaluation.id = "EVAL"; draft_evaluation.evaluation_id = evaluation.id
    evaluation.save_revision(draft_evaluation)
    evaluation.save_revision(deepcopy(evaluation.active_revision()))
    attachments = [
        EntityAttachment("ATT-E", "blast_event", "BE-P", "photo", "face", "", "Face", "a.jpg", "a.jpg",
            "assessment/a.jpg", date(2026, 8, 4), "", "image/jpeg", 12, NOW),
        EntityAttachment("ATT-V", "assessment_evaluation", "EVAL", "document", "report", "", "Report",
            "r.pdf", "r.pdf", "assessment/r.pdf", date(2026, 8, 4), "", "application/pdf", 34, NOW),
    ]
    return AssessmentDomainState(datasets, [production, contour], [area], [card], [evaluation], attachments)


@pytest.fixture
def rich_state():
    return build_rich_state()


def invalid(state, text=None):
    with pytest.raises(AssessmentStateValidationError, match=text):
        validate_assessment_state(state)


def test_empty_state_is_valid(): validate_assessment_state(AssessmentDomainState())
def test_rich_state_is_valid(rich_state): validate_assessment_state(rich_state)


def test_duplicate_top_level_ids(rich_state):
    rich_state.blast_events.append(deepcopy(rich_state.blast_events[0])); invalid(rich_state, "duplicate ID")


def test_duplicate_revision_ids(rich_state):
    rich_state.blast_events[0].geometry_revisions[1].id = rich_state.blast_events[0].geometry_revisions[0].id
    invalid(rich_state, "duplicate ID")


def test_duplicate_revision_numbers(rich_state):
    rich_state.blast_events[0].geometry_revisions[1].revision_number = 1; invalid(rich_state, "revision numbers")


def test_wrong_revision_parent(rich_state):
    rich_state.blast_events[0].geometry_revisions[0].blast_event_id = "other"; invalid(rich_state, "wrong parent")


def test_missing_active_revision(rich_state):
    rich_state.blast_events[0].active_geometry_revision_id = "missing"; invalid(rich_state, "does not exist")


def test_multiple_active_datasets(rich_state):
    rich_state.datasets[0].is_active = True; invalid(rich_state, "at most one dataset")


def test_missing_source_dataset(rich_state):
    object.__setattr__(rich_state.assessment_areas[0].geometry_revisions[0], "source_dataset_id", "missing")
    invalid(rich_state, "source dataset")


def test_invalid_blast_geometry_link(rich_state):
    rich_state.assessment_areas[0].event_links[0].geometry_revision_id = "missing"; invalid(rich_state, "invalid BlastEvent")


def test_technical_card_geometry_from_other_event(rich_state):
    rich_state.technical_cards[0].revisions[0].geometry_revision_id = "BE-C-R1"; invalid(rich_state, "another event")


def test_evaluation_geometry_from_other_area(rich_state):
    other = deepcopy(rich_state.assessment_areas[0]); other.id = "AA2"
    other.geometry_revisions = [deepcopy(other.geometry_revisions[0])]
    object.__setattr__(other.geometry_revisions[0], "id", "AA2-R1")
    object.__setattr__(other.geometry_revisions[0], "assessment_area_id", "AA2")
    other.active_geometry_revision_id = "AA2-R1"; other.event_links = []
    rich_state.assessment_areas.append(other)
    rich_state.evaluations[0].revisions[0].assessment_area_geometry_revision_id = "AA2-R1"
    invalid(rich_state, "another Assessment Area")


def test_missing_attachment_owner(rich_state):
    rich_state.attachments[0].owner_id = "missing"; invalid(rich_state, "owner does not exist")


def test_absolute_attachment_path(rich_state):
    rich_state.attachments[0].relative_path = "/tmp/a.jpg"; invalid(rich_state, "relative")


def test_negative_attachment_size(rich_state):
    rich_state.attachments[0].file_size_bytes = -1; invalid(rich_state, "non-negative")


@pytest.mark.parametrize("target,attribute", [("event", "elevation"), ("revision", "elevation")])
def test_non_finite_elevations(rich_state, target, attribute):
    obj = rich_state.blast_events[0] if target == "event" else rich_state.blast_events[0].geometry_revisions[0]
    setattr(obj, attribute, math.inf); invalid(rich_state, "finite")


def test_invalid_elevation_interval(rich_state):
    revision = rich_state.assessment_areas[0].geometry_revisions[0]
    object.__setattr__(revision, "lower_elevation", revision.upper_elevation)
    invalid(rich_state, "below")


def test_none_change_reason_is_valid(rich_state):
    assert rich_state.assessment_areas[0].geometry_revisions[-1].change_reason is None
    validate_assessment_state(rich_state)


def test_public_technical_card_serialization(rich_state):
    card = rich_state.technical_cards[0]
    assert BlastEventTechnicalCard.from_dict(card.to_dict()).to_dict() == card.to_dict()


def test_public_evaluation_serialization(rich_state):
    evaluation = rich_state.evaluations[0]
    assert AssessmentAreaEvaluation.from_dict(evaluation.to_dict()).to_dict() == evaluation.to_dict()


def test_mapper_import_creates_no_engine_or_session():
    code = """
import sqlalchemy, sqlalchemy.orm
sqlalchemy.create_engine=lambda *a, **k: (_ for _ in ()).throw(AssertionError('engine'))
sqlalchemy.orm.Session=lambda *a, **k: (_ for _ in ()).throw(AssertionError('session'))
import repositories.assessment_state_mapper
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_mapper_imports_no_qt_ui_or_storage():
    sys.modules.pop("repositories.assessment_state_mapper", None)
    before = set(sys.modules); importlib.import_module("repositories.assessment_state_mapper")
    added = set(sys.modules) - before
    forbidden = ("PySide6", "PyQt6", "ui", "prototype_2d.blast_event_storage")
    assert not any(name == prefix or name.startswith(prefix + ".") for name in added for prefix in forbidden)


def test_duplicate_link_identity(rich_state):
    duplicate = deepcopy(rich_state.assessment_areas[0].event_links[0]); duplicate.id = "LINK-DUP"
    rich_state.assessment_areas[0].event_links.append(duplicate); invalid(rich_state, "duplicate AssessmentEventLink")


def test_duplicate_card_for_event(rich_state):
    card = deepcopy(rich_state.technical_cards[0]); card.id = "TC-2"
    for revision in card.revisions: revision.technical_card_id = card.id; revision.id += "-copy"
    rich_state.technical_cards.append(card); invalid(rich_state, "more than one technical card")


def test_unsupported_attachment_owner_type(rich_state):
    rich_state.attachments[1].owner_type = "unknown"; invalid(rich_state, "unsupported attachment")


def test_event_active_id_must_match_flags(rich_state):
    rich_state.blast_events[0].geometry_revisions[0].is_active = True
    invalid(rich_state, "multiple active")


def test_card_event_type_must_match_event(rich_state):
    rich_state.technical_cards[0].revisions[0].event_type = "contour"
    invalid(rich_state, "event_type differs")


def test_duplicate_evaluation_for_area(rich_state):
    evaluation = deepcopy(rich_state.evaluations[0]); evaluation.id = "EVAL-2"
    for revision in evaluation.revisions:
        revision.evaluation_id = evaluation.id; revision.id += "-copy"
    rich_state.evaluations.append(evaluation); invalid(rich_state, "more than one evaluation")


def test_link_requires_created_at_after_canonicalization(rich_state):
    rich_state.assessment_areas[0].event_links[0].created_at = None
    invalid(rich_state, "no created_at")
