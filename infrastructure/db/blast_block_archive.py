"""SQLAlchemy adapter for the focused BlastBlock archive command."""
from datetime import datetime, timezone

from database.models import BlastBlock


class SqlAlchemyBlastBlockArchivePersistence:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def set_archived(self, block_id: int, archived: bool, actor_id: int) -> None:
        del actor_id  # Existing archive behaviour deliberately has no audit entry.
        with self._session_factory.begin() as session:
            block = session.get(BlastBlock, block_id)
            if block is None:
                raise ValueError("Blast block not found")
            block.is_archived = archived
            block.archived_at = datetime.now(timezone.utc) if archived else None
