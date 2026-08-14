"""Add the shared explosive-product catalogue without seed data."""
from alembic import op
import sqlalchemy as sa

revision = "0003_explosive_catalog"
down_revision = "0002_workflow_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "explosive_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("density_kg_m3", sa.Numeric(12, 3)),
        sa.Column("cartridge_diameter_mm", sa.Numeric(10, 3)),
        sa.Column("cartridge_mass_kg", sa.Numeric(10, 4)),
        sa.Column("display_color", sa.String(7), nullable=False),
        sa.Column("default_pitch_m", sa.Numeric(10, 4)),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('bulk', 'cartridge')", name="ck_explosive_products_kind"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_explosive_products_name"),
        sa.CheckConstraint("display_color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_explosive_products_color"),
        sa.CheckConstraint(
            "(kind = 'bulk' AND density_kg_m3 > 0 AND cartridge_diameter_mm IS NULL "
            "AND cartridge_mass_kg IS NULL AND default_pitch_m IS NULL) OR "
            "(kind = 'cartridge' AND density_kg_m3 IS NULL AND cartridge_diameter_mm > 0 "
            "AND cartridge_mass_kg > 0)", name="ck_explosive_products_kind_fields"),
        sa.CheckConstraint("default_pitch_m IS NULL OR default_pitch_m > 0",
                           name="ck_explosive_products_pitch"),
        sa.UniqueConstraint("name", name="uq_explosive_products_name"),
    )
    op.create_index("ix_explosive_products_is_enabled", "explosive_products", ["is_enabled"])


def downgrade() -> None:
    op.drop_table("explosive_products")
