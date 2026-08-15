"""Restore explosive classification and optional cartridge length metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0006_explosive_product_metadata"
down_revision = "0005_explosive_charge_form"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("explosive_products", sa.Column(
        "explosive_class", sa.String(20), nullable=False, server_default="other"))
    op.add_column("explosive_products", sa.Column("cartridge_length_mm", sa.Numeric(10, 3)))
    op.create_check_constraint("ck_explosive_products_class", "explosive_products",
        "explosive_class IN ('anfo', 'emulsion', 'heavy_anfo', 'slurry', 'dynamite', 'other')")
    op.create_check_constraint("ck_explosive_products_cartridge_length", "explosive_products",
        "cartridge_length_mm IS NULL OR cartridge_length_mm > 0")
    op.create_check_constraint("ck_explosive_products_form_cartridge_length", "explosive_products",
        "charge_form = 'cartridged' OR cartridge_length_mm IS NULL")


def downgrade():
    op.drop_constraint("ck_explosive_products_form_cartridge_length", "explosive_products", type_="check")
    op.drop_constraint("ck_explosive_products_cartridge_length", "explosive_products", type_="check")
    op.drop_constraint("ck_explosive_products_class", "explosive_products", type_="check")
    op.drop_column("explosive_products", "cartridge_length_mm")
    op.drop_column("explosive_products", "explosive_class")
