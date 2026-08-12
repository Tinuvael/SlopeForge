"""SQLAlchemy adapter for the focused BlastBlock archive command."""
from datetime import datetime, timezone

from database.models import BlastBlock
from infrastructure.db.domain_version import guard_domain_versions


class SqlAlchemyBlastBlockArchivePersistence:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def set_archived(self, block_id: int, expected_version: int,
                     archived: bool, actor_id: int) -> int:
        del actor_id  # Existing archive behaviour deliberately has no audit entry.
        with self._session_factory.begin() as session:
            block = session.get(BlastBlock, block_id)
            if block is None:
                raise ValueError("Blast block not found")
            new_version = guard_domain_versions(
                session, {block.domain_id: expected_version})[block.domain_id]
            block.is_archived = archived
            block.archived_at = datetime.now(timezone.utc) if archived else None
            return new_version
