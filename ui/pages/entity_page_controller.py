"""Small persistence controller shared by normal entity and geometry pages."""
from copy import deepcopy
from repositories.assessment_state_repository import AssessmentStateRepository
from prototype_2d.technical_card import TechnicalCardService
from prototype_2d.wall_assessment import AssessmentAreaEvaluationService
from prototype_2d.assessment_event_link_service import AssessmentEventLinkService
from prototype_2d.entity_attachments import EntityAttachmentService

class EntityPageController:
    def __init__(self, context, domain_id):
        self.context=context; self.domain_id=domain_id; self.repository=AssessmentStateRepository(context.session_factory)
        loaded=self.repository.load_for_domain(domain_id); self.site_id=loaded.site_id; self.workspace_id=loaded.workspace_id; self.state=loaded.state
        self.technical_cards=TechnicalCardService(self.state); self.evaluations=AssessmentAreaEvaluationService(self.state); self.links=AssessmentEventLinkService(self.state)
        self.attachments=EntityAttachmentService(self.state,context.storage_root / "slopeforge_state.json",self.save)
    def save(self):
        if not self.context.current_user.can_edit:
            raise PermissionError("2D Assessment is read-only for the current user")
        saved=self.repository.replace_for_domain(self.domain_id,self.state); self.workspace_id=saved.workspace_id
    def event_for_block(self, block_id): return next((e for e in self.state.blast_events if e.blast_block_id==block_id and e.event_type=="production"),None)
    def area(self, area_id): return next((a for a in self.state.assessment_areas if a.id==area_id),None)
    def technical_card_draft(self,event): return self.technical_cards.edit_or_create(event)
    def save_technical_card(self,card,revision,status):
        count=len(card.revisions); active=card.active_revision_id
        try: card.save_revision(revision,status=status); self.save()
        except Exception:
            del card.revisions[count:]; card.active_revision_id=active; raise
    def evaluation_draft(self,area):
        existing=next((e for e in reversed(self.state.evaluations) if e.assessment_area_id==area.id),None)
        if existing and existing.active_revision():return existing,deepcopy(existing.active_revision())
        if existing:return self.evaluations.new_draft(existing,area)
        return self.evaluations.new_evaluation(area)
    def ensure_evaluation_owner(self,area,evaluation=None):
        existing=next((e for e in self.state.evaluations if e.assessment_area_id==area.id),None)
        if existing:return existing
        owner=evaluation or self.evaluations.create_evaluation(area)
        if owner.assessment_area_id!=area.id:raise ValueError("evaluation owner belongs to another Assessment Area")
        self.state.evaluations.append(owner)
        try:self.save()
        except Exception:
            self.state.evaluations.remove(owner); raise
        return owner
    def prepare_evaluation_attachment_owner(self,area,evaluation=None):
        """Prepare an attachment owner in memory; attachment save persists it atomically."""
        existing=next((e for e in self.state.evaluations if e.assessment_area_id==area.id),None)
        if existing:return existing,None
        owner=evaluation or self.evaluations.create_evaluation(area)
        if owner.assessment_area_id!=area.id:raise ValueError("evaluation owner belongs to another Assessment Area")
        self.state.evaluations.append(owner)
        def rollback():
            if owner in self.state.evaluations and not owner.revisions:
                self.state.evaluations.remove(owner)
        return owner,rollback
    def save_evaluation(self,evaluation,revision,status):
        present=evaluation in self.state.evaluations; count=len(evaluation.revisions); active=evaluation.active_revision_id
        try:
            evaluation.save_revision(revision,status)
            if not present:self.state.evaluations.append(evaluation)
            self.save()
        except Exception:
            del evaluation.revisions[count:]; evaluation.active_revision_id=active
            if not present and evaluation in self.state.evaluations:self.state.evaluations.remove(evaluation)
            raise
