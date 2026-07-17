"""add user administration fields and remember tokens

Revision ID: 20260715_0003
Revises: 20260715_0002
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260715_0003"
down_revision = "20260715_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("updated_by_user_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_foreign_key("fk_users_created_by_user_id_users", "users", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_users_updated_by_user_id_users", "users", "users", ["updated_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_users_created_by_user_id", "users", ["created_by_user_id"])
    op.create_index("ix_users_updated_by_user_id", "users", ["updated_by_user_id"])

    op.create_table(
        "remember_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_remember_tokens_user_id", "remember_tokens", ["user_id"])
    op.create_index("ix_remember_tokens_token_hash", "remember_tokens", ["token_hash"])
    op.create_index("ix_remember_tokens_expires_at", "remember_tokens", ["expires_at"])
    op.create_index("ix_remember_tokens_revoked_at", "remember_tokens", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_remember_tokens_revoked_at", table_name="remember_tokens")
    op.drop_index("ix_remember_tokens_expires_at", table_name="remember_tokens")
    op.drop_index("ix_remember_tokens_token_hash", table_name="remember_tokens")
    op.drop_index("ix_remember_tokens_user_id", table_name="remember_tokens")
    op.drop_table("remember_tokens")
    op.drop_index("ix_users_updated_by_user_id", table_name="users")
    op.drop_index("ix_users_created_by_user_id", table_name="users")
    op.drop_constraint("fk_users_updated_by_user_id_users", "users", type_="foreignkey")
    op.drop_constraint("fk_users_created_by_user_id_users", "users", type_="foreignkey")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "updated_by_user_id")
    op.drop_column("users", "created_by_user_id")
    op.drop_column("users", "last_login_at")
