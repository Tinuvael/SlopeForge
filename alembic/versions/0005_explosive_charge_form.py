"""Add explicit explosive charge form."""
from alembic import op
import sqlalchemy as sa

revision = "0005_explosive_charge_form"
down_revision = "0004_charge_presets"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("explosive_products", sa.Column(
        "charge_form", sa.String(20), nullable=False, server_default="bulk"))
    op.execute("UPDATE explosive_products SET charge_form = CASE "
               "WHEN kind = 'cartridge' THEN 'cartridged' ELSE 'bulk' END")
    op.create_check_constraint("ck_explosive_products_charge_form", "explosive_products",
        "charge_form IN ('bulk', 'pumpable', 'cartridged')")


def downgrade():
    op.drop_constraint("ck_explosive_products_charge_form", "explosive_products", type_="check")
    op.drop_column("explosive_products", "charge_form")
