"""replace horizontal Assessment geometry with ordered boundary tracing

Revision ID: 20260813_0012
Revises: 20260812_0011
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260813_0012"
down_revision = "20260812_0011"
branch_labels = None
depends_on = None

def upgrade():
    # Development data used the incompatible horizon model and cannot be represented faithfully.
    op.execute("DELETE FROM assessment_areas")
    op.drop_constraint("ck_assessment_area_geometry_revisions_elevation_order", "assessment_area_geometry_revisions", type_="check")
    op.drop_constraint("ck_assessment_area_geometry_revisions_selection_object", "assessment_area_geometry_revisions", type_="check")
    op.drop_constraint("ck_assessment_area_geometry_revisions_slices_array", "assessment_area_geometry_revisions", type_="check")
    op.drop_constraint("assessment_area_geometry_revisions_source_dataset_id_fkey", "assessment_area_geometry_revisions", type_="foreignkey")
    op.drop_column("assessment_area_geometry_revisions", "source_dataset_id")
    op.drop_column("assessment_area_geometry_revisions", "selection_polygon_json")
    op.drop_column("assessment_area_geometry_revisions", "horizon_slices_json")
    op.drop_column("assessment_area_geometry_revisions", "lower_elevation_m")
    op.drop_column("assessment_area_geometry_revisions", "upper_elevation_m")
    op.add_column("assessment_area_geometry_revisions", sa.Column("boundary_json", postgresql.JSONB(), nullable=False))
    op.add_column("assessment_area_geometry_revisions", sa.Column("min_elevation_m", sa.Numeric(12, 3), nullable=True))
    op.add_column("assessment_area_geometry_revisions", sa.Column("max_elevation_m", sa.Numeric(12, 3), nullable=True))
    op.create_check_constraint("ck_assessment_area_geometry_revisions_boundary_object", "assessment_area_geometry_revisions", "jsonb_typeof(boundary_json) = 'object'")

def downgrade():
    # The two models are intentionally incompatible; the MVP database is disposable.
    op.execute("DELETE FROM assessment_areas")
    op.drop_constraint("ck_assessment_area_geometry_revisions_boundary_object", "assessment_area_geometry_revisions", type_="check")
    op.drop_column("assessment_area_geometry_revisions", "boundary_json")
    op.drop_column("assessment_area_geometry_revisions", "min_elevation_m")
    op.drop_column("assessment_area_geometry_revisions", "max_elevation_m")
    op.add_column("assessment_area_geometry_revisions", sa.Column("source_dataset_id", sa.Integer(), nullable=False))
    op.add_column("assessment_area_geometry_revisions", sa.Column("selection_polygon_json", postgresql.JSONB(), nullable=False))
    op.add_column("assessment_area_geometry_revisions", sa.Column("horizon_slices_json", postgresql.JSONB(), nullable=False))
    op.add_column("assessment_area_geometry_revisions", sa.Column("lower_elevation_m", sa.Numeric(12, 3), nullable=False))
    op.add_column("assessment_area_geometry_revisions", sa.Column("upper_elevation_m", sa.Numeric(12, 3), nullable=False))
    op.create_foreign_key("assessment_area_geometry_revisions_source_dataset_id_fkey",
                          "assessment_area_geometry_revisions", "project_lines_datasets",
                          ["source_dataset_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_assessment_area_geometry_revisions_elevation_order",
                               "assessment_area_geometry_revisions", "lower_elevation_m < upper_elevation_m")
    op.create_check_constraint("ck_assessment_area_geometry_revisions_selection_object",
                               "assessment_area_geometry_revisions", "jsonb_typeof(selection_polygon_json) = 'object'")
    op.create_check_constraint("ck_assessment_area_geometry_revisions_slices_array",
                               "assessment_area_geometry_revisions", "jsonb_typeof(horizon_slices_json) = 'array'")
