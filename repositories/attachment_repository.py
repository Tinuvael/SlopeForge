from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import Attachment


@dataclass(frozen=True)
class AttachmentRow:
    id: int
    attachment_kind: str
    subtype: str | None
    original_filename: str
    stored_relative_path: str
    mime_type: str | None
    file_size_bytes: int | None
    file_date: date | None
    description: str | None


class AttachmentRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def count_for_block(self, blast_block_id: int, attachment_kind: str | None = None) -> int:
        with self.session_factory() as session:
            stmt = select(func.count(Attachment.id)).where(Attachment.blast_block_id == blast_block_id)
            if attachment_kind:
                stmt = stmt.where(Attachment.attachment_kind == attachment_kind)
            return int(session.scalar(stmt) or 0)

    def list_for_block(self, blast_block_id: int, attachment_kind: str, limit: int = 5) -> list[AttachmentRow]:
        with self.session_factory() as session:
            attachments = list(
                session.scalars(
                    select(Attachment)
                    .where(Attachment.blast_block_id == blast_block_id, Attachment.attachment_kind == attachment_kind)
                    .order_by(Attachment.created_at.desc(), Attachment.id.desc())
                    .limit(limit)
                )
            )
            return [self._to_row(item) for item in attachments]

    @staticmethod
    def _to_row(item: Attachment) -> AttachmentRow:
        return AttachmentRow(
            id=item.id,
            attachment_kind=item.attachment_kind,
            subtype=item.subtype,
            original_filename=item.original_filename,
            stored_relative_path=item.stored_relative_path,
            mime_type=item.mime_type,
            file_size_bytes=item.file_size_bytes,
            file_date=item.file_date,
            description=item.description,
        )
