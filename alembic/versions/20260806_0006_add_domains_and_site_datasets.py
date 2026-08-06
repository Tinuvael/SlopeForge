"""Add Site domains and Site-scoped Project Lines.

Revision ID: 20260806_0006
Revises: 20260804_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20260806_0006"
down_revision = "20260804_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("site_id", "name", name="uq_domains_site_name"))
    op.create_index("ix_domains_site_id", "domains", ["site_id"])
    # One deterministic compatibility Domain per existing Site; IDs are never used as engineering identifiers.
    op.execute(sa.text("""INSERT INTO domains (site_id, name)
        SELECT s.id, 'Основной домен' FROM sites s
        WHERE NOT EXISTS (SELECT 1 FROM domains d WHERE d.site_id=s.id)"""))
    op.add_column("blast_blocks", sa.Column("domain_id", sa.Integer(), nullable=True))
    op.add_column("assessment_workspaces", sa.Column("domain_id", sa.Integer(), nullable=True))
    op.add_column("project_lines_datasets", sa.Column("site_id", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE blast_blocks b SET domain_id=d.id FROM domains d WHERE d.site_id=b.site_id"))
    op.execute(sa.text("UPDATE assessment_workspaces w SET domain_id=d.id FROM domains d WHERE d.site_id=w.site_id"))
    op.execute(sa.text("UPDATE project_lines_datasets p SET site_id=w.site_id FROM assessment_workspaces w WHERE w.id=p.workspace_id"))
    op.alter_column("blast_blocks", "domain_id", nullable=False)
    op.alter_column("assessment_workspaces", "domain_id", nullable=False)
    op.alter_column("project_lines_datasets", "site_id", nullable=False)
    op.create_foreign_key("fk_blast_blocks_domain_id", "blast_blocks", "domains", ["domain_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_assessment_workspaces_domain_id", "assessment_workspaces", "domains", ["domain_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_project_lines_datasets_site_id", "project_lines_datasets", "sites", ["site_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_assessment_workspaces_domain_id", "assessment_workspaces", ["domain_id"])
    op.create_unique_constraint("uq_project_lines_datasets_site_domain_id", "project_lines_datasets", ["site_id", "domain_id"])
    op.create_index("ix_blast_blocks_domain_id", "blast_blocks", ["domain_id"])
    op.create_index("ix_blast_blocks_domain_block_number", "blast_blocks", ["domain_id", "block_number"])
    op.create_index("ix_project_lines_datasets_site_id", "project_lines_datasets", ["site_id"])
    op.create_index("ix_project_lines_datasets_one_active_per_site", "project_lines_datasets", ["site_id"], unique=True, postgresql_where=sa.text("is_active"))
    op.drop_constraint("uq_project_lines_datasets_workspace_domain_id", "project_lines_datasets", type_="unique")
    op.drop_index("ix_project_lines_datasets_one_active_per_workspace", table_name="project_lines_datasets")
    op.drop_index("ix_project_lines_datasets_workspace_id", table_name="project_lines_datasets")
    op.drop_index("ix_blast_blocks_site_block_number", table_name="blast_blocks")
    op.drop_constraint("assessment_workspaces_site_id_key", "assessment_workspaces", type_="unique")
    op.drop_column("project_lines_datasets", "workspace_id")
    op.drop_column("assessment_workspaces", "site_id")
    op.drop_column("blast_blocks", "site_id")


def downgrade():
    # The old schema can represent only one Assessment workspace per Site.
    # Keep the lowest workspace id deterministically and cascade-delete the
    # additional Domain workspaces before restoring UNIQUE(site_id).
    op.execute(sa.text("""DELETE FROM assessment_workspaces w
        USING domains d
        WHERE w.domain_id=d.id AND w.id <> (
            SELECT min(w2.id) FROM assessment_workspaces w2
            JOIN domains d2 ON d2.id=w2.domain_id WHERE d2.site_id=d.site_id
        )"""))
    op.add_column("blast_blocks", sa.Column("site_id", sa.Integer(), nullable=True))
    op.add_column("assessment_workspaces", sa.Column("site_id", sa.Integer(), nullable=True))
    op.add_column("project_lines_datasets", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE blast_blocks b SET site_id=d.site_id FROM domains d WHERE d.id=b.domain_id"))
    op.execute(sa.text("UPDATE assessment_workspaces w SET site_id=d.site_id FROM domains d WHERE d.id=w.domain_id"))
    op.execute(sa.text("UPDATE project_lines_datasets p SET workspace_id=w.id FROM assessment_workspaces w JOIN domains d ON d.id=w.domain_id WHERE d.site_id=p.site_id"))
    op.alter_column("blast_blocks", "site_id", nullable=False); op.alter_column("assessment_workspaces", "site_id", nullable=False)
    # A Site with datasets but no workspace cannot be represented by the old schema.
    op.execute(sa.text("DELETE FROM project_lines_datasets WHERE workspace_id IS NULL")); op.alter_column("project_lines_datasets", "workspace_id", nullable=False)
    op.create_foreign_key("blast_blocks_site_id_fkey", "blast_blocks", "sites", ["site_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("assessment_workspaces_site_id_fkey", "assessment_workspaces", "sites", ["site_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("project_lines_datasets_workspace_id_fkey", "project_lines_datasets", "assessment_workspaces", ["workspace_id"], ["id"], ondelete="CASCADE")
    op.create_unique_constraint("assessment_workspaces_site_id_key", "assessment_workspaces", ["site_id"])
    op.create_unique_constraint("uq_project_lines_datasets_workspace_domain_id", "project_lines_datasets", ["workspace_id", "domain_id"])
    op.create_index("ix_blast_blocks_site_block_number", "blast_blocks", ["site_id", "block_number"])
    op.create_index("ix_project_lines_datasets_workspace_id", "project_lines_datasets", ["workspace_id"])
    op.create_index("ix_project_lines_datasets_one_active_per_workspace", "project_lines_datasets", ["workspace_id"], unique=True, postgresql_where=sa.text("is_active"))
    for table, constraint in [("project_lines_datasets","fk_project_lines_datasets_site_id"),("assessment_workspaces","fk_assessment_workspaces_domain_id"),("blast_blocks","fk_blast_blocks_domain_id")]: op.drop_constraint(constraint, table, type_="foreignkey")
    op.drop_constraint("uq_project_lines_datasets_site_domain_id", "project_lines_datasets", type_="unique")
    op.drop_constraint("uq_assessment_workspaces_domain_id", "assessment_workspaces", type_="unique")
    op.drop_index("ix_project_lines_datasets_one_active_per_site", table_name="project_lines_datasets"); op.drop_index("ix_project_lines_datasets_site_id", table_name="project_lines_datasets")
    op.drop_index("ix_blast_blocks_domain_block_number", table_name="blast_blocks"); op.drop_index("ix_blast_blocks_domain_id", table_name="blast_blocks")
    op.drop_column("project_lines_datasets", "site_id"); op.drop_column("assessment_workspaces", "domain_id"); op.drop_column("blast_blocks", "domain_id")
    op.drop_index("ix_domains_site_id", table_name="domains"); op.drop_table("domains")
