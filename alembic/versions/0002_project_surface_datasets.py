"""Add metadata for revisioned Project design and actual surface datasets."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_project_surface_datasets"
down_revision = "0001_mvp_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_surface_datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("logical_id", sa.String(length=255), nullable=False),
        sa.Column("dataset_kind", sa.String(length=20), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_by_user_id", sa.Integer(), nullable=True),
        sa.Column("source_format", sa.String(length=20), nullable=False),
        sa.Column("source_files_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("vertex_count", sa.Integer(), nullable=False),
        sa.Column("triangle_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "dataset_kind IN ('design', 'actual')",
            name="ck_project_surface_datasets_kind",
        ),
        sa.CheckConstraint(
            "source_format IN ('dxf', 'datamine')",
            name="ck_project_surface_datasets_format",
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name="ck_project_surface_datasets_revision_positive",
        ),
        sa.CheckConstraint(
            "vertex_count >= 3", name="ck_project_surface_datasets_vertex_count"
        ),
        sa.CheckConstraint(
            "triangle_count > 0", name="ck_project_surface_datasets_triangle_count"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_files_json) = 'array'",
            name="ck_project_surface_datasets_source_files_array",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["imported_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_id", "logical_id", name="uq_project_surface_datasets_site_logical_id"
        ),
        sa.UniqueConstraint(
            "site_id",
            "dataset_kind",
            "revision_number",
            name="uq_project_surface_datasets_site_kind_revision",
        ),
    )
    op.create_index(
        "ix_project_surface_datasets_site_kind_revision",
        "project_surface_datasets",
        ["site_id", "dataset_kind", "revision_number"],
        unique=False,
    )
    op.create_index(
        "ix_project_surface_datasets_imported_at",
        "project_surface_datasets",
        ["imported_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_surface_datasets_imported_at",
        table_name="project_surface_datasets",
    )
    op.drop_index(
        "ix_project_surface_datasets_site_kind_revision",
        table_name="project_surface_datasets",
    )
    op.drop_table("project_surface_datasets")
