"""add Domain optimistic concurrency version

Revision ID: 20260812_0009
Revises: 20260809_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_0009"
down_revision = "20260809_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "domains", sa.Column("version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("domains", "version")
