"""allow an omitted Assessment Area geometry change reason

Revision ID: 20260804_0005
Revises: 20260804_0004
"""
from alembic import op

revision = "20260804_0005"
down_revision = "20260804_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("assessment_area_geometry_revisions", "change_reason", nullable=True)


def downgrade() -> None:
    op.execute("UPDATE assessment_area_geometry_revisions SET change_reason = '' WHERE change_reason IS NULL")
    op.alter_column("assessment_area_geometry_revisions", "change_reason", nullable=False)
