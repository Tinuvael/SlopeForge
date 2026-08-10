"""Thin UI adapter for entity-page application services."""
from app.use_case_factory import create_entity_editing_session
from application.services.assessment_event_links import AssessmentEventLinkService
from application.services.attachments import EntityAttachmentService


class EntityPageController:
    def __init__(self, context, domain_id):
        self.context = context
        self.editing = create_entity_editing_session(context, domain_id)
        self.domain_id = self.editing.domain_id
        self.state = self.editing.state
        self.links = AssessmentEventLinkService(self.state)
        self.attachments = EntityAttachmentService(
            self.state, context.storage_root / "slopeforge_state.json", self.editing.save)

    @property
    def site_id(self):
        return self.editing.site_id

    @property
    def workspace_id(self):
        return self.editing.workspace_id

    def save(self):
        return self.editing.save()

    def event_for_block(self, block_id):
        return next((event for event in self.state.blast_events
                     if event.blast_block_id == block_id and event.event_type == "production"), None)

    def area(self, area_id):
        return next((area for area in self.state.assessment_areas if area.id == area_id), None)

    def technical_card_draft(self, event):
        return self.editing.technical_card_draft(event)

    def save_technical_card(self, card, revision, status):
        return self.editing.save_technical_card(card, revision, status)

    def evaluation_draft(self, area):
        return self.editing.evaluation_draft(area)

    def ensure_evaluation_owner(self, area, evaluation=None):
        return self.editing.ensure_evaluation_owner(area, evaluation)

    def prepare_evaluation_attachment_owner(self, area, evaluation=None):
        return self.editing.prepare_evaluation_attachment_owner(area, evaluation)

    def save_evaluation(self, evaluation, revision, status):
        return self.editing.save_evaluation(evaluation, revision, status)
