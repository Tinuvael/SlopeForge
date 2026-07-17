"""add audit log entries

Revision ID: 20260715_0002
Revises: 20260714_0001
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260715_0002"
down_revision = "20260714_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_block_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.String(length=80), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["blast_block_id"], ["blast_blocks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("action IN ('create', 'update', 'delete', 'attach', 'detach')", name="ck_audit_log_entries_action"),
        sa.CheckConstraint("entity_type IN ('blast_block', 'attachment', 'rock_mass_profile', 'rock_structure', 'blast_design', 'drilling_pattern', 'wall_assessment')", name="ck_audit_log_entries_entity_type"),
    )
    op.create_index("ix_audit_log_entries_blast_block_id", "audit_log_entries", ["blast_block_id"])
    op.create_index("ix_audit_log_entries_user_id", "audit_log_entries", ["user_id"])
    op.create_index("ix_audit_log_entries_created_at", "audit_log_entries", ["created_at"])
    op.create_index("ix_audit_log_entries_action", "audit_log_entries", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_entries_action", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_created_at", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_user_id", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_blast_block_id", table_name="audit_log_entries")
    op.drop_table("audit_log_entries")
