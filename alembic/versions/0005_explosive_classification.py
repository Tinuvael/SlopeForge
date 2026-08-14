"""Separate explosive charge form from explosive class."""
from alembic import op
import sqlalchemy as sa

revision = "0005_explosive_classification"
down_revision = "0004_charge_presets"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("explosive_products", sa.Column("charge_form", sa.String(20)))
    op.add_column("explosive_products", sa.Column("explosive_class", sa.String(20),
                                                   nullable=False, server_default="other"))
    op.add_column("explosive_products", sa.Column("cartridge_length_mm", sa.Numeric(10, 3)))
    op.execute("UPDATE explosive_products SET charge_form = CASE WHEN kind = 'cartridge' THEN 'cartridged' ELSE 'bulk' END")
    op.alter_column("explosive_products", "charge_form", nullable=False)
    op.drop_constraint("ck_explosive_products_kind_fields", "explosive_products", type_="check")
    op.create_check_constraint("ck_explosive_products_charge_form", "explosive_products",
        "charge_form IN ('bulk', 'pumpable', 'cartridged')")
    op.create_check_constraint("ck_explosive_products_class", "explosive_products",
        "explosive_class IN ('anfo', 'emulsion', 'heavy_anfo', 'slurry', 'dynamite', 'other')")
    op.create_check_constraint("ck_explosive_products_form_fields", "explosive_products",
        "((charge_form IN ('bulk','pumpable') AND kind='bulk' AND density_kg_m3 > 0 "
        "AND cartridge_diameter_mm IS NULL AND cartridge_mass_kg IS NULL AND cartridge_length_mm IS NULL) OR "
        "(charge_form='cartridged' AND kind='cartridge' AND density_kg_m3 IS NULL "
        "AND cartridge_diameter_mm > 0 AND cartridge_mass_kg > 0 "
        "AND (cartridge_length_mm IS NULL OR cartridge_length_mm > 0)))")

def downgrade():
    op.drop_constraint("ck_explosive_products_form_fields", "explosive_products", type_="check")
    op.drop_constraint("ck_explosive_products_class", "explosive_products", type_="check")
    op.drop_constraint("ck_explosive_products_charge_form", "explosive_products", type_="check")
    op.create_check_constraint("ck_explosive_products_kind_fields", "explosive_products",
        "(kind = 'bulk' AND density_kg_m3 > 0 AND cartridge_diameter_mm IS NULL AND cartridge_mass_kg IS NULL AND default_pitch_m IS NULL) OR "
        "(kind = 'cartridge' AND density_kg_m3 IS NULL AND cartridge_diameter_mm > 0 AND cartridge_mass_kg > 0)")
    op.drop_column("explosive_products", "cartridge_length_mm")
    op.drop_column("explosive_products", "explosive_class")
    op.drop_column("explosive_products", "charge_form")
