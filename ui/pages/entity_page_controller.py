"""Thin UI adapter for entity-page application services."""
from app.use_case_factory import create_entity_editing_session
from application.services.attachments import EntityAttachmentService


class EntityPageController:
    def __init__(self, context, domain_id):
        self.context = context
        self.editing = create_entity_editing_session(context, domain_id)
        self.domain_id = self.editing.domain_id
        self.state = self.editing.state
        self.links = self.editing.links
        self.attachments = EntityAttachmentService(
            self.state, context.storage_root / "slopeforge_state.json",
            on_add=self._persist_attachment_add,
            on_update=self.editing.update_attachment_metadata,
            on_delete=self.editing.delete_attachment_metadata)

    def _persist_attachment_add(self, attachments):
        owner = None
        if attachments and attachments[0].owner_type == "assessment_evaluation":
            owner = next((item for item in self.state.evaluations
                          if item.id == attachments[0].owner_id), None)
        self.editing.add_attachment_metadata_batch(attachments, owner)

    @property
    def site_id(self):
        return self.editing.site_id

    @property
    def expected_version(self):
        """Canonical version for every command issued by this open entity page."""
        return self.editing.expected_version

    def event(self, event_id):
        return next((event for event in self.state.blast_events if event.id == event_id), None)

    def production_event(self, event_id):
        event = self.event(event_id)
        return event if event is not None and event.event_type == "production" else None

    def area(self, area_id):
        return next((area for area in self.state.assessment_areas if area.id == area_id), None)

    def technical_card_draft(self, event):
        return self.editing.technical_card_draft(event)

    def save_technical_card(self, card, revision, status, planned_date=...):
        return self.editing.save_technical_card(card, revision, status, planned_date)

    def evaluation_draft(self, area):
        return self.editing.evaluation_draft(area)

    def ensure_evaluation_owner(self, area, evaluation=None):
        return self.editing.ensure_evaluation_owner(area, evaluation)

    def prepare_evaluation_attachment_owner(self, area, evaluation=None):
        return self.editing.prepare_evaluation_attachment_owner(area, evaluation)

    def save_evaluation(self, evaluation, revision, status):
        return self.editing.save_evaluation(evaluation, revision, status)

    def set_assessment_area_archived(self, area, archived):
        return self.editing.set_assessment_area_archived(area, archived)

    def set_contour_event_archived(self, event, archived):
        return self.editing.set_contour_event_archived(event, archived)

    def update_contour_metadata(self, event, **values):
        return self.editing.update_contour_metadata(event, **values)

    def update_assessment_area_metadata(self, area, **values):
        return self.editing.update_assessment_area_metadata(area, **values)

    def reimport_blast_event_geometry(self, event, path):
        return self.editing.reimport_blast_event_geometry(event, path)

    def confirm_event_link(self, area, link_id):
        return self.editing.confirm_event_link(area, link_id)

    def exclude_event_link(self, area, link_id):
        return self.editing.exclude_event_link(area, link_id)

    def restore_event_link(self, area, link_id):
        return self.editing.restore_event_link(area, link_id)

    def add_manual_event_link(self, area, event_id):
        return self.editing.add_manual_event_link(area, event_id)

    def refresh_event_link_suggestions(self, area):
        return self.editing.refresh_event_link_suggestions(area)

    def preview_assessment_event_links(self, boundary):
        return self.editing.preview_assessment_event_links(boundary)

    def save_assessment_area_geometry(self, **values):
        return self.editing.save_assessment_area_geometry(**values)
