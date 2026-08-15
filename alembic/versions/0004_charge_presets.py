"""Add Project-wide charge design presets and explicit explosive charge form."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_charge_presets"
down_revision = "0003_explosive_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("explosive_products", sa.Column("charge_form", sa.String(20), nullable=False, server_default="bulk"))
    op.execute("UPDATE explosive_products SET charge_form = 'cartridged' WHERE kind = 'cartridge'")
    op.create_check_constraint("ck_explosive_products_charge_form", "explosive_products",
        "charge_form IN ('bulk', 'pumpable', 'cartridged')")
    op.create_table("charge_design_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("components_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("site_id", "name", name="uq_charge_design_presets_site_name"))
    op.create_index("ix_charge_design_presets_site_id", "charge_design_presets", ["site_id"])


def downgrade():
    op.drop_table("charge_design_presets")
    op.drop_constraint("ck_explosive_products_charge_form", "explosive_products", type_="check")
    op.drop_column("explosive_products", "charge_form")
