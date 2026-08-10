"""Small desktop composition helpers (not a dependency-injection container)."""
from application.use_cases.create_blast_event import CreateBlastEvent
from infrastructure.db.blast_event_creation import SqlAlchemyBlastEventCreationPersistence


def create_blast_event_use_case(context):
    return CreateBlastEvent(SqlAlchemyBlastEventCreationPersistence(context.session_factory))
