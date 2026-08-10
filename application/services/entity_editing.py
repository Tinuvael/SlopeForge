"""Application coordinator for editing entities in one Assessment Domain."""
from __future__ import annotations

from copy import deepcopy

from application.ports.assessment_state import AssessmentStatePersistence
from application.services.assessment_event_links import AssessmentEventLinkService
from application.services.blast_events import BlastEventService
from domain.assessment.evaluation import AssessmentAreaEvaluationService
from domain.blasting.technical_card import TechnicalCardService


class AssessmentEditingSession:
    """Owns the live graph and its replace-all persistence workflows."""

    def __init__(self, persistence: AssessmentStatePersistence, domain_id: int, *,
                 actor_id: int, can_edit: bool):
        snapshot = persistence.load(domain_id)
        self._persistence = persistence
        self.domain_id = snapshot.domain_id
        self.site_id = snapshot.site_id
        self.workspace_id = snapshot.workspace_id
        self.state = snapshot.state
        self.actor_id = actor_id
        self.can_edit = can_edit
        self.technical_cards = TechnicalCardService(self.state)
        self.evaluations = AssessmentAreaEvaluationService(self.state)
        self.links = AssessmentEventLinkService(self.state)

    def _require_edit(self) -> None:
        if not self.can_edit:
            raise PermissionError("2D Assessment is read-only for the current user")

    def save(self) -> None:
        self._require_edit()
        snapshot = self._persistence.save(self.domain_id, self.state)
        # Keep the live object graph: widgets hold references into it.
        self.workspace_id = snapshot.workspace_id

    def _save_archive_change(self, entity, archived: bool) -> None:
        self._require_edit()
        previous = (entity.is_archived, entity.archived_at, entity.archive_reason)
        try:
            entity.archive() if archived else entity.restore()
            self.save()
        except Exception:
            entity.is_archived, entity.archived_at, entity.archive_reason = previous
            raise

    def set_assessment_area_archived(self, area, archived: bool) -> None:
        if area not in self.state.assessment_areas:
            raise ValueError("Assessment Area not found in this Domain")
        self._save_archive_change(area, archived)

    def set_contour_event_archived(self, event, archived: bool) -> None:
        if event not in self.state.blast_events:
            raise ValueError("BlastEvent not found in this Domain")
        if event.event_type != "contour":
            raise ValueError("Only contour BlastEvents can use contour archive")
        self._save_archive_change(event, archived)

    def reimport_blast_event_geometry(self, event, path):
        self._require_edit()
        if event not in self.state.blast_events:
            raise ValueError("BlastEvent not found in this Domain")
        count = len(event.geometry_revisions)
        active_id = event.active_geometry_revision_id
        active_flags = [revision.is_active for revision in event.geometry_revisions]
        try:
            revision = BlastEventService(self.state).reimport_geometry(event, path)
            self.save()
            return revision
        except Exception:
            del event.geometry_revisions[count:]
            event.active_geometry_revision_id = active_id
            for existing, is_active in zip(event.geometry_revisions, active_flags):
                existing.is_active = is_active
            raise

    def _mutate_links(self, area, operation, *args):
        self._require_edit()
        if area not in self.state.assessment_areas:
            raise ValueError("Assessment Area not found in this Domain")
        # Preserve the original list and objects; only status is mutable in-place.
        original_links = list(area.event_links)
        original_statuses = [(link, link.status) for link in original_links]
        try:
            result = operation(area, *args)
            self.save()
            return result
        except Exception:
            area.event_links[:] = original_links
            for link, status in original_statuses:
                link.status = status
            raise

    def confirm_event_link(self, area, link_id):
        return self._mutate_links(area, self.links.confirm_link, link_id)

    def exclude_event_link(self, area, link_id):
        return self._mutate_links(area, self.links.exclude_link, link_id)

    def restore_event_link(self, area, link_id):
        return self._mutate_links(area, self.links.restore_suggestion, link_id)

    def add_manual_event_link(self, area, blast_event_id):
        return self._mutate_links(area, self.links.add_manual_link, blast_event_id)

    def refresh_event_link_suggestions(self, area):
        return self._mutate_links(area, self.links.refresh_suggestions)

    def technical_card_draft(self, event):
        return self.technical_cards.edit_or_create(event)

    def save_technical_card(self, card, revision, status):
        self._require_edit()
        count = len(card.revisions)
        active = card.active_revision_id
        try:
            card.save_revision(revision, status=status)
            self.save()
        except Exception:
            del card.revisions[count:]
            card.active_revision_id = active
            raise

    def evaluation_draft(self, area):
        existing = next(
            (item for item in reversed(self.state.evaluations)
             if item.assessment_area_id == area.id), None,
        )
        if existing and existing.active_revision():
            return existing, deepcopy(existing.active_revision())
        if existing:
            return self.evaluations.new_draft(existing, area)
        return self.evaluations.new_evaluation(area)

    def ensure_evaluation_owner(self, area, evaluation=None):
        """Persist an empty owner when an explicit non-attachment caller needs it."""
        self._require_edit()
        owner, rollback = self.prepare_evaluation_attachment_owner(area, evaluation)
        if rollback is None:
            return owner
        try:
            self.save()
        except Exception:
            rollback()
            raise
        return owner

    def prepare_evaluation_attachment_owner(self, area, evaluation=None):
        """Prepare a lazy owner; the attachment save persists owner and file metadata."""
        self._require_edit()
        existing = next(
            (item for item in self.state.evaluations
             if item.assessment_area_id == area.id), None,
        )
        if existing:
            return existing, None
        owner = evaluation or self.evaluations.create_evaluation(area)
        if owner.assessment_area_id != area.id:
            raise ValueError("evaluation owner belongs to another Assessment Area")
        self.state.evaluations.append(owner)

        def rollback():
            if owner in self.state.evaluations and not owner.revisions:
                self.state.evaluations.remove(owner)

        return owner, rollback

    def save_evaluation(self, evaluation, revision, status):
        self._require_edit()
        present = evaluation in self.state.evaluations
        count = len(evaluation.revisions)
        active = evaluation.active_revision_id
        try:
            evaluation.save_revision(revision, status)
            if not present:
                self.state.evaluations.append(evaluation)
            self.save()
        except Exception:
            del evaluation.revisions[count:]
            evaluation.active_revision_id = active
            if not present and evaluation in self.state.evaluations:
                self.state.evaluations.remove(evaluation)
            raise
