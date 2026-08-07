"""make Assessment domain-scoped and Project Lines site-scoped

Revision ID: 20260807_0006
Revises: 20260804_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20260807_0006"
down_revision = "20260804_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", "name", name="uq_domains_site_name"),
    )
    op.create_index("ix_domains_site_id", "domains", ["site_id"])
    op.execute("""
        INSERT INTO domains (site_id, name)
        SELECT s.id, 'Основной домен'
        FROM sites s
        WHERE EXISTS (SELECT 1 FROM assessment_workspaces w WHERE w.site_id = s.id)
    """)

    op.add_column("assessment_workspaces", sa.Column("domain_id", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE assessment_workspaces w SET domain_id = d.id
        FROM domains d WHERE d.site_id = w.site_id AND d.name = 'Основной домен'
    """)
    op.create_foreign_key("fk_assessment_workspaces_domain_id", "assessment_workspaces", "domains",
                          ["domain_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_assessment_workspaces_domain_id", "assessment_workspaces", ["domain_id"])
    op.alter_column("assessment_workspaces", "domain_id", nullable=False)

    op.add_column("project_lines_datasets", sa.Column("site_id", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE project_lines_datasets p SET site_id = w.site_id
        FROM assessment_workspaces w WHERE w.id = p.workspace_id
    """)
    op.add_column("project_lines_datasets", sa.Column("is_archived", sa.Boolean(),
                  nullable=False, server_default=sa.false()))
    op.add_column("project_lines_datasets", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.create_foreign_key("fk_project_lines_datasets_site_id", "project_lines_datasets", "sites",
                          ["site_id"], ["id"], ondelete="RESTRICT")
    op.alter_column("project_lines_datasets", "site_id", nullable=False)

    op.drop_index("ix_project_lines_datasets_one_active_per_workspace", table_name="project_lines_datasets")
    op.drop_index("ix_project_lines_datasets_workspace_id", table_name="project_lines_datasets")
    op.drop_constraint("uq_project_lines_datasets_workspace_domain_id", "project_lines_datasets", type_="unique")
    op.create_unique_constraint("uq_project_lines_datasets_site_domain_id", "project_lines_datasets",
                                ["site_id", "domain_id"])
    op.create_check_constraint("ck_project_lines_datasets_archived_not_active",
                               "project_lines_datasets", "NOT (is_archived AND is_active)")
    op.create_index("ix_project_lines_datasets_site_id", "project_lines_datasets", ["site_id"])
    op.create_index("ix_project_lines_datasets_one_active_per_site", "project_lines_datasets", ["site_id"],
                    unique=True, postgresql_where=sa.text("is_active"))

    op.drop_constraint("project_lines_datasets_workspace_id_fkey", "project_lines_datasets", type_="foreignkey")
    op.drop_column("project_lines_datasets", "workspace_id")
    op.drop_constraint("assessment_workspaces_site_id_key", "assessment_workspaces", type_="unique")
    op.drop_constraint("assessment_workspaces_site_id_fkey", "assessment_workspaces", type_="foreignkey")
    op.drop_column("assessment_workspaces", "site_id")


def downgrade() -> None:
    op.add_column("assessment_workspaces", sa.Column("site_id", sa.Integer(), nullable=True))
    op.execute("UPDATE assessment_workspaces w SET site_id = d.site_id FROM domains d WHERE d.id = w.domain_id")
    # Project Lines may have been imported before a Domain workspace existed.
    # The old schema requires every Dataset to point at a workspace, so create
    # a temporary compatibility Domain for a Domain-less Site if necessary,
    # then create one workspace from the Site's lowest Domain id.
    op.execute("""
        INSERT INTO domains (site_id, name)
        SELECT DISTINCT p.site_id, 'Основной домен'
        FROM project_lines_datasets p
        WHERE NOT EXISTS (SELECT 1 FROM domains d WHERE d.site_id = p.site_id)
    """)
    op.execute("""
        INSERT INTO assessment_workspaces (domain_id, site_id)
        SELECT min(d.id), p.site_id
        FROM (SELECT DISTINCT site_id FROM project_lines_datasets) p
        JOIN domains d ON d.site_id = p.site_id
        WHERE NOT EXISTS (
            SELECT 1 FROM assessment_workspaces w WHERE w.site_id = p.site_id
        )
        GROUP BY p.site_id
    """)
    # The 0005 schema can represent only one workspace per Site.  Keep the
    # lowest integer PK deterministically; deleting the others intentionally
    # cascades their Domain-owned Assessment rows before UNIQUE(site_id) is
    # restored.  Site Project Lines are retained independently and attached to
    # that surviving workspace below.
    op.execute("""
        DELETE FROM assessment_workspaces w
        USING assessment_workspaces keep
        WHERE w.site_id = keep.site_id AND w.id > keep.id
    """)
    op.create_foreign_key("assessment_workspaces_site_id_fkey", "assessment_workspaces", "sites",
                          ["site_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("assessment_workspaces_site_id_key", "assessment_workspaces", ["site_id"])
    op.alter_column("assessment_workspaces", "site_id", nullable=False)
    op.add_column("project_lines_datasets", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.execute("""UPDATE project_lines_datasets p SET workspace_id = w.id
                  FROM assessment_workspaces w WHERE w.site_id = p.site_id""")
    op.create_foreign_key("project_lines_datasets_workspace_id_fkey", "project_lines_datasets",
                          "assessment_workspaces", ["workspace_id"], ["id"], ondelete="CASCADE")
    op.alter_column("project_lines_datasets", "workspace_id", nullable=False)
    op.drop_index("ix_project_lines_datasets_one_active_per_site", table_name="project_lines_datasets")
    op.drop_index("ix_project_lines_datasets_site_id", table_name="project_lines_datasets")
    op.drop_constraint("ck_project_lines_datasets_archived_not_active", "project_lines_datasets", type_="check")
    op.drop_constraint("uq_project_lines_datasets_site_domain_id", "project_lines_datasets", type_="unique")
    op.create_unique_constraint("uq_project_lines_datasets_workspace_domain_id", "project_lines_datasets",
                                ["workspace_id", "domain_id"])
    op.create_index("ix_project_lines_datasets_workspace_id", "project_lines_datasets", ["workspace_id"])
    op.create_index("ix_project_lines_datasets_one_active_per_workspace", "project_lines_datasets",
                    ["workspace_id"], unique=True, postgresql_where=sa.text("is_active"))
    op.drop_constraint("fk_project_lines_datasets_site_id", "project_lines_datasets", type_="foreignkey")
    op.drop_column("project_lines_datasets", "archived_at")
    op.drop_column("project_lines_datasets", "is_archived")
    op.drop_column("project_lines_datasets", "site_id")
    op.drop_constraint("uq_assessment_workspaces_domain_id", "assessment_workspaces", type_="unique")
    op.drop_constraint("fk_assessment_workspaces_domain_id", "assessment_workspaces", type_="foreignkey")
    op.drop_column("assessment_workspaces", "domain_id")
    op.drop_index("ix_domains_site_id", table_name="domains")
    op.drop_table("domains")
