"""initial PostgreSQL foundation

Revision ID: 20260714_0001
Revises: 
Create Date: 2026-07-14
"""
from __future__ import annotations

from alembic import op
from sqlalchemy.dialects import postgresql

from database.base import Base
from database import models  # noqa: F401

revision = "20260714_0001"
down_revision = None
branch_labels = None
depends_on = None

ENUMS = [
    postgresql.ENUM("admin", "editor", "viewer", name="user_role"),
    postgresql.ENUM("planned", "blasted", "assessed", name="blast_block_status"),
    postgresql.ENUM("joint_set", "tectonic_structure", name="structure_type"),
    postgresql.ENUM("production", "buffer", "contour", name="drilling_role"),
    postgresql.ENUM("explosive", "stemming", "air_deck", name="charge_segment_type"),
    postgresql.ENUM("good", "satisfactory", "poor", name="wall_rating"),
    postgresql.ENUM("photo", "document", name="attachment_kind"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)
