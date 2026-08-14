"""Add Project-wide charge-design presets."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_charge_presets"
down_revision = "0003_explosive_catalog"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("charge_design_presets",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("site_id",sa.Integer(),sa.ForeignKey("sites.id",ondelete="CASCADE"),nullable=False),
        sa.Column("name",sa.String(255),nullable=False),
        sa.Column("components_json",postgresql.JSONB(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint("length(btrim(name)) > 0",name="ck_charge_design_presets_name"),
        sa.CheckConstraint("jsonb_typeof(components_json) = 'array'",name="ck_charge_design_presets_components_array"),
        sa.UniqueConstraint("site_id","name",name="uq_charge_design_presets_site_name"))
    op.create_index("ix_charge_design_presets_site_id","charge_design_presets",["site_id"])
def downgrade(): op.drop_table("charge_design_presets")
