"""Derive Blast workflow status and make BlastEvent.event_date canonical.

The downgrade necessarily loses the historical manual lifecycle value: the
recreated legacy status is deterministically set to ``planned``.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_derive_blast_workflow_status"
down_revision = "0001_mvp_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE blast_events AS event
           SET event_date = block.planned_blast_date
          FROM blast_blocks AS block
         WHERE event.blast_block_id = block.id
           AND event.event_type = 'production'
           AND event.event_date IS NULL
           AND block.planned_blast_date IS NOT NULL
    """))
    op.drop_index("ix_blast_blocks_status", table_name="blast_blocks")
    op.drop_column("blast_blocks", "planned_blast_date")
    op.drop_column("blast_blocks", "status")
    sa.Enum(name="blast_block_status").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    legacy = sa.Enum("planned", "blasted", "assessed", name="blast_block_status")
    legacy.create(op.get_bind(), checkfirst=True)
    op.add_column("blast_blocks", sa.Column(
        "status", legacy, nullable=False, server_default="planned"))
    op.add_column("blast_blocks", sa.Column("planned_blast_date", sa.Date(), nullable=True))
    op.create_index("ix_blast_blocks_status", "blast_blocks", ["status"])
    op.execute(sa.text("""
        UPDATE blast_blocks AS block
           SET planned_blast_date = event.event_date
          FROM blast_events AS event
         WHERE event.blast_block_id = block.id
           AND event.event_type = 'production'
    """))
    op.alter_column("blast_blocks", "status", server_default=None)
