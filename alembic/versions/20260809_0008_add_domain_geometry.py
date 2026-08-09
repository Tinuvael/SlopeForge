"""add current plan-view Domain Geometry

Revision ID: 20260809_0008
Revises: 20260807_0007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260809_0008"
down_revision = "20260807_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "domain_geometries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("polygons_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("source_file_name", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("jsonb_typeof(polygons_json) = 'array'", name="ck_domain_geometries_polygons_array"),
        sa.CheckConstraint("source_kind IN ('imported', 'drawn')", name="ck_domain_geometries_source_kind"),
        sa.UniqueConstraint("domain_id", name="uq_domain_geometries_domain_id"),
    )
    op.create_index("ix_domain_geometries_domain_id", "domain_geometries", ["domain_id"])


def downgrade() -> None:
    op.drop_index("ix_domain_geometries_domain_id", table_name="domain_geometries")
    op.drop_table("domain_geometries")
