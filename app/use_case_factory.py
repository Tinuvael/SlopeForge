"""Small desktop composition helpers (not a dependency-injection container)."""
from application.use_cases.create_blast_event import CreateBlastEvent
from infrastructure.db.blast_event_creation import SqlAlchemyBlastEventCreationPersistence
from application.services.entity_editing import AssessmentEditingSession
from infrastructure.db.assessment_state import SqlAlchemyAssessmentStatePersistence
from application.use_cases.set_blast_block_archived import SetBlastBlockArchived
from infrastructure.db.blast_block_archive import SqlAlchemyBlastBlockArchivePersistence


def create_blast_event_use_case(context):
    return CreateBlastEvent(SqlAlchemyBlastEventCreationPersistence(context.session_factory))


def create_entity_editing_session(context, domain_id):
    user = context.current_user
    return AssessmentEditingSession(
        SqlAlchemyAssessmentStatePersistence(context.session_factory),
        domain_id,
        actor_id=user.id,
        can_edit=user.can_edit,
    )


def create_set_blast_block_archived_use_case(context):
    return SetBlastBlockArchived(
        SqlAlchemyBlastBlockArchivePersistence(context.session_factory)
    )
