"""Remove legacy Mine and BlastBlock persistence.

Revision ID: 0007_remove_mine_blastblock
Revises: 0006_explosive_product_metadata

The current MVP development database is disposable. This migration deliberately
prefers the final single-entity schema over compatibility data copying.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_remove_mine_blastblock"
down_revision = "0006_explosive_product_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Production Block metadata now lives directly on BlastEvent.
    op.add_column("blast_events", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("blast_events", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_blast_events_created_by_user_id_users",
        "blast_events", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_blast_events_created_by_user_id", "blast_events", ["created_by_user_id"])

    # Current dev audit data is intentionally disposable. Recreate the table as
    # entity-generic groundwork for #121 rather than carrying blast_block_id.
    op.drop_table("audit_log_entries")
    op.create_table(
        "audit_log_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('create', 'update', 'delete', 'attach', 'detach')", name="ck_audit_log_entries_action"),
    )
    op.create_index("ix_audit_log_entries_user_id", "audit_log_entries", ["user_id"])
    op.create_index("ix_audit_log_entries_action", "audit_log_entries", ["action"])
    op.create_index("ix_audit_log_entries_created_at", "audit_log_entries", ["created_at"])
    op.create_index("ix_audit_log_entries_entity", "audit_log_entries", ["entity_type", "entity_id"])

    op.drop_constraint("uq_blast_events_blast_block_id", "blast_events", type_="unique")
    op.drop_constraint("ck_blast_events_block_production_only", "blast_events", type_="check")
    op.drop_constraint("blast_events_blast_block_id_fkey", "blast_events", type_="foreignkey")
    op.drop_column("blast_events", "blast_block_id")
    op.drop_table("blast_blocks")
    op.execute("DROP TYPE IF EXISTS blast_block_status")

    op.drop_constraint("sites_mine_id_fkey", "sites", type_="foreignkey")
    op.drop_index("ix_sites_mine_id", table_name="sites")
    op.drop_column("sites", "mine_id")
    op.drop_table("mines")


def downgrade() -> None:
    # Downgrade restores the old *shape* only. The destructive upgrade never
    # promises to reconstruct disposable Mine/BlastBlock/audit records.
    op.create_table(
        "mines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mines_name", "mines", ["name"])
    op.add_column("sites", sa.Column("mine_id", sa.Integer(), nullable=True))
    op.create_foreign_key("sites_mine_id_fkey", "sites", "mines", ["mine_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_sites_mine_id", "sites", ["mine_id"])

    status_enum = sa.Enum("planned", "blasted", "assessed", name="blast_block_status")
    status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "blast_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("block_number", sa.String(length=80), nullable=False),
        sa.Column("horizon_m", sa.Numeric(10, 2), nullable=True),
        sa.Column("planned_blast_date", sa.Date(), nullable=True),
        sa.Column("status", status_enum, nullable=False, server_default="planned"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_blast_blocks_domain_id", "blast_blocks", ["domain_id"])
    op.create_index("ix_blast_blocks_domain_block_number", "blast_blocks", ["domain_id", "block_number"])
    op.create_index("ix_blast_blocks_is_archived", "blast_blocks", ["is_archived"])
    op.create_index("ix_blast_blocks_status", "blast_blocks", ["status"])
    op.create_index("ix_blast_blocks_created_by_user_id", "blast_blocks", ["created_by_user_id"])
    op.add_column("blast_events", sa.Column("blast_block_id", sa.Integer(), nullable=True))
    op.create_foreign_key("blast_events_blast_block_id_fkey", "blast_events", "blast_blocks", ["blast_block_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_blast_events_blast_block_id", "blast_events", ["blast_block_id"])
    op.create_check_constraint("ck_blast_events_block_production_only", "blast_events", "blast_block_id IS NULL OR event_type = 'production'")

    op.drop_table("audit_log_entries")
    op.create_table(
        "audit_log_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_block_id", sa.Integer(), sa.ForeignKey("blast_blocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.String(length=80), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('create', 'update', 'delete', 'attach', 'detach')", name="ck_audit_log_entries_action"),
        sa.CheckConstraint("entity_type IN ('blast_block', 'attachment', 'rock_mass_profile', 'rock_structure', 'blast_design', 'drilling_pattern', 'wall_assessment')", name="ck_audit_log_entries_entity_type"),
    )
    op.create_index("ix_audit_log_entries_blast_block_id", "audit_log_entries", ["blast_block_id"])
    op.create_index("ix_audit_log_entries_user_id", "audit_log_entries", ["user_id"])
    op.create_index("ix_audit_log_entries_action", "audit_log_entries", ["action"])
    op.create_index("ix_audit_log_entries_created_at", "audit_log_entries", ["created_at"])

    op.drop_index("ix_blast_events_created_by_user_id", table_name="blast_events")
    op.drop_constraint("fk_blast_events_created_by_user_id_users", "blast_events", type_="foreignkey")
    op.drop_column("blast_events", "created_by_user_id")
    op.drop_column("blast_events", "comment")
