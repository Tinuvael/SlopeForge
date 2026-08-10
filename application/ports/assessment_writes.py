"""Focused write boundary for Assessment commands (Phase 5B)."""
from __future__ import annotations

from typing import Protocol

from domain.assessment.entities import AssessmentArea
from domain.assessment.evaluation import AssessmentAreaEvaluation
from domain.attachments.entities import EntityAttachment
from domain.blasting.entities import BlastEvent, BlastEventGeometryRevision
from domain.blasting.technical_card import (
    BlastEventTechnicalCard, BlastEventTechnicalCardRevision,
)


class AssessmentWrites(Protocol):
    """Explicit writes; deliberately no whole-aggregate ``save`` operation."""

    def persist_area_archive(self, domain_id: int, area: AssessmentArea) -> int: ...
    def persist_contour_archive(self, domain_id: int, event: BlastEvent) -> int: ...
    def append_blast_geometry_revision(self, domain_id: int, event_id: str,
                                       revision: BlastEventGeometryRevision) -> int: ...
    def persist_technical_card_revision(self, domain_id: int,
            card: BlastEventTechnicalCard,
            revision: BlastEventTechnicalCardRevision) -> int: ...
    def persist_assessment_area_geometry(self, domain_id: int,
                                         area: AssessmentArea) -> int: ...
    def synchronize_area_links(self, domain_id: int, area: AssessmentArea) -> int: ...
    def persist_evaluation_owner(self, domain_id: int,
                                 evaluation: AssessmentAreaEvaluation) -> int: ...
    def persist_evaluation_revision(self, domain_id: int,
            evaluation: AssessmentAreaEvaluation, revision) -> int: ...
    def add_attachment_metadata_batch(self, domain_id: int,
            attachments: list[EntityAttachment],
            evaluation_owner: AssessmentAreaEvaluation | None = None) -> int: ...
    def update_attachment_metadata(self, domain_id: int,
                                   attachment: EntityAttachment) -> int: ...
    def delete_attachment_metadata(self, domain_id: int, attachment_id: str) -> int: ...
