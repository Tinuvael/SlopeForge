"""Move BlastBlock ownership from Site to Domain.

Revision ID: 20260807_0007
Revises: 20260807_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260807_0007"
down_revision = "20260807_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("blast_blocks", sa.Column("domain_id", sa.Integer(), nullable=True))
    op.add_column("blast_blocks", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("blast_blocks", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_blast_blocks_is_archived", "blast_blocks", ["is_archived"])
    # Sites with legacy blocks must have a deterministic fallback Domain.
    op.execute("""
        INSERT INTO domains (site_id, name, description, created_at, updated_at)
        SELECT DISTINCT b.site_id, 'Основной домен',
               'Создан автоматически при переносе взрывных блоков', now(), now()
        FROM blast_blocks b
        WHERE NOT EXISTS (SELECT 1 FROM domains d WHERE d.site_id = b.site_id)
    """)
    # A linked production event is the strongest ownership signal.
    op.execute("""
        UPDATE blast_blocks b SET domain_id = aw.domain_id
        FROM blast_events be
        JOIN assessment_workspaces aw ON aw.id = be.workspace_id
        WHERE be.blast_block_id = b.id AND be.event_type = 'production'
    """)
    # Otherwise select the oldest Domain in the legacy Site.
    op.execute("""
        UPDATE blast_blocks b SET domain_id = (
            SELECT min(d.id) FROM domains d WHERE d.site_id = b.site_id
        ) WHERE b.domain_id IS NULL
    """)
    op.alter_column("blast_blocks", "domain_id", nullable=False)
    op.create_foreign_key("fk_blast_blocks_domain_id_domains", "blast_blocks", "domains", ["domain_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_blast_blocks_domain_id", "blast_blocks", ["domain_id"])
    op.create_index("ix_blast_blocks_domain_block_number", "blast_blocks", ["domain_id", "block_number"])
    op.drop_index("ix_blast_blocks_site_block_number", table_name="blast_blocks")
    op.drop_index("ix_blast_blocks_site_id", table_name="blast_blocks")
    op.drop_constraint("blast_blocks_site_id_fkey", "blast_blocks", type_="foreignkey")
    op.drop_column("blast_blocks", "site_id")


def downgrade():
    op.add_column("blast_blocks", sa.Column("site_id", sa.Integer(), nullable=True))
    op.execute("UPDATE blast_blocks b SET site_id = d.site_id FROM domains d WHERE d.id = b.domain_id")
    op.alter_column("blast_blocks", "site_id", nullable=False)
    op.create_foreign_key("blast_blocks_site_id_fkey", "blast_blocks", "sites", ["site_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_blast_blocks_site_id", "blast_blocks", ["site_id"])
    op.create_index("ix_blast_blocks_site_block_number", "blast_blocks", ["site_id", "block_number"])
    op.drop_index("ix_blast_blocks_domain_block_number", table_name="blast_blocks")
    op.drop_index("ix_blast_blocks_domain_id", table_name="blast_blocks")
    op.drop_constraint("fk_blast_blocks_domain_id_domains", "blast_blocks", type_="foreignkey")
    op.drop_column("blast_blocks", "domain_id")
    op.drop_index("ix_blast_blocks_is_archived", table_name="blast_blocks")
    op.drop_column("blast_blocks", "archived_at")
    op.drop_column("blast_blocks", "is_archived")
