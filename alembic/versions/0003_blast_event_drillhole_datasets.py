"""Add revisioned design and actual drillhole datasets for Blast Events."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_blast_event_drillhole_datasets"
down_revision = "0002_project_surface_datasets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blast_event_drillhole_datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("blast_event_id", sa.Integer(), nullable=False),
        sa.Column("logical_id", sa.String(length=255), nullable=False),
        sa.Column("dataset_kind", sa.String(length=20), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("matched_design_dataset_id", sa.Integer(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_by_user_id", sa.Integer(), nullable=True),
        sa.Column("source_format", sa.String(length=20), nullable=False),
        sa.Column("source_files_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("holes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matches_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hole_count", sa.Integer(), nullable=False),
        sa.Column("total_drilling_length_m", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "dataset_kind IN ('design', 'actual')",
            name="ck_blast_event_drillhole_datasets_kind",
        ),
        sa.CheckConstraint(
            "((dataset_kind = 'design' AND matched_design_dataset_id IS NULL) "
            "OR (dataset_kind = 'actual' AND matched_design_dataset_id IS NOT NULL))",
            name="ck_blast_event_drillhole_datasets_design_provenance",
        ),
        sa.CheckConstraint(
            "source_format IN ('dxf', 'datamine')",
            name="ck_blast_event_drillhole_datasets_format",
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name="ck_blast_event_drillhole_datasets_revision_positive",
        ),
        sa.CheckConstraint(
            "hole_count > 0",
            name="ck_blast_event_drillhole_datasets_hole_count",
        ),
        sa.CheckConstraint(
            "total_drilling_length_m > 0",
            name="ck_blast_event_drillhole_datasets_total_length",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_files_json) = 'array'",
            name="ck_blast_event_drillhole_datasets_source_files_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(holes_json) = 'array'",
            name="ck_blast_event_drillhole_datasets_holes_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(summary_json) = 'object'",
            name="ck_blast_event_drillhole_datasets_summary_object",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(matches_json) = 'array'",
            name="ck_blast_event_drillhole_datasets_matches_array",
        ),
        sa.ForeignKeyConstraint(["blast_event_id"], ["blast_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["matched_design_dataset_id"],
            ["blast_event_drillhole_datasets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "blast_event_id",
            "logical_id",
            name="uq_blast_event_drillhole_datasets_event_logical_id",
        ),
        sa.UniqueConstraint(
            "blast_event_id",
            "dataset_kind",
            "revision_number",
            name="uq_blast_event_drillhole_datasets_event_kind_revision",
        ),
    )
    op.create_index(
        "ix_blast_event_drillhole_datasets_event_kind_revision",
        "blast_event_drillhole_datasets",
        ["blast_event_id", "dataset_kind", "revision_number"],
        unique=False,
    )
    op.create_index(
        "ix_blast_event_drillhole_datasets_imported_at",
        "blast_event_drillhole_datasets",
        ["imported_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_blast_event_drillhole_datasets_imported_at",
        table_name="blast_event_drillhole_datasets",
    )
    op.drop_index(
        "ix_blast_event_drillhole_datasets_event_kind_revision",
        table_name="blast_event_drillhole_datasets",
    )
    op.drop_table("blast_event_drillhole_datasets")
