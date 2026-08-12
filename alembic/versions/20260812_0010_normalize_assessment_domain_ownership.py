"""normalize Assessment ownership directly under Domain

Revision ID: 20260812_0010
Revises: 20260812_0009
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_0010"
down_revision = "20260812_0009"
branch_labels = None
depends_on = None

_LOGICAL_TABLES = (
    "project_lines_datasets", "blast_event_geometry_revisions",
    "blast_event_technical_cards", "blast_event_technical_card_revisions",
    "assessment_area_geometry_revisions", "assessment_event_links",
    "assessment_area_evaluations", "assessment_area_evaluation_revisions",
    "assessment_entity_attachments",
)

_CONSTRAINT_RENAMES = (
    ("project_lines_datasets", "uq_project_lines_datasets_site_domain_id", "uq_project_lines_datasets_site_logical_id"),
    ("blast_event_geometry_revisions", "uq_blast_event_geometry_revisions_parent_domain_id", "uq_blast_event_geometry_revisions_parent_logical_id"),
    ("blast_event_technical_cards", "uq_blast_event_technical_cards_domain_id", "uq_blast_event_technical_cards_logical_id"),
    ("blast_event_technical_card_revisions", "uq_technical_card_revisions_parent_domain_id", "uq_technical_card_revisions_parent_logical_id"),
    ("assessment_area_geometry_revisions", "uq_assessment_area_geometry_revisions_parent_domain_id", "uq_assessment_area_geometry_revisions_parent_logical_id"),
    ("assessment_event_links", "uq_assessment_event_links_parent_domain_id", "uq_assessment_event_links_parent_logical_id"),
    ("assessment_area_evaluations", "uq_assessment_area_evaluations_domain_id", "uq_assessment_area_evaluations_logical_id"),
    ("assessment_area_evaluation_revisions", "uq_assessment_evaluation_revisions_parent_domain_id", "uq_assessment_evaluation_revisions_parent_logical_id"),
    ("assessment_entity_attachments", "uq_assessment_entity_attachments_domain_id", "uq_assessment_entity_attachments_logical_id"),
)


def upgrade() -> None:
    # Preserve the public/domain-layer identifiers while giving ownership FKs
    # the unambiguous domain_id name.
    for table in _LOGICAL_TABLES + ("blast_events", "assessment_areas"):
        op.alter_column(table, "domain_id", new_column_name="logical_id")

    for table in ("blast_events", "assessment_areas"):
        op.add_column(table, sa.Column("domain_id", sa.Integer(), nullable=True))
        op.execute(sa.text(f"""UPDATE {table} entity SET domain_id = workspace.domain_id
            FROM assessment_workspaces workspace WHERE workspace.id = entity.workspace_id"""))
        op.alter_column(table, "domain_id", nullable=False)
        op.create_foreign_key(f"fk_{table}_domain_id", table, "domains", ["domain_id"], ["id"], ondelete="RESTRICT")

    op.drop_constraint("uq_blast_events_workspace_domain_id", "blast_events", type_="unique")
    op.drop_index("ix_blast_events_workspace_id", table_name="blast_events")
    op.create_unique_constraint("uq_blast_events_domain_logical_id", "blast_events", ["domain_id", "logical_id"])
    op.create_index("ix_blast_events_domain_id", "blast_events", ["domain_id"])
    op.drop_constraint("blast_events_workspace_id_fkey", "blast_events", type_="foreignkey")
    op.drop_column("blast_events", "workspace_id")

    op.drop_constraint("uq_assessment_areas_workspace_domain_id", "assessment_areas", type_="unique")
    op.drop_index("ix_assessment_areas_workspace_id", table_name="assessment_areas")
    op.create_unique_constraint("uq_assessment_areas_domain_logical_id", "assessment_areas", ["domain_id", "logical_id"])
    op.create_index("ix_assessment_areas_domain_id", "assessment_areas", ["domain_id"])
    op.drop_constraint("assessment_areas_workspace_id_fkey", "assessment_areas", type_="foreignkey")
    op.drop_column("assessment_areas", "workspace_id")

    op.drop_table("assessment_workspaces")
    # Constraint names are documentation too: rename those that described a
    # logical identifier as a Domain FK. PostgreSQL keeps their definitions
    # valid through the column rename.
    for table, old, new in _CONSTRAINT_RENAMES:
        op.execute(sa.text(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}"))



def downgrade() -> None:
    op.create_table(
        "assessment_workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("domain_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_foreign_key("fk_assessment_workspaces_domain_id", "assessment_workspaces",
                          "domains", ["domain_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_assessment_workspaces_domain_id",
                                "assessment_workspaces", ["domain_id"])
    op.execute("INSERT INTO assessment_workspaces (domain_id) SELECT id FROM domains")
    for table in ("blast_events", "assessment_areas"):
        op.add_column(table, sa.Column("workspace_id", sa.Integer(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} entity SET workspace_id=workspace.id FROM assessment_workspaces workspace WHERE workspace.domain_id=entity.domain_id"))
        op.alter_column(table, "workspace_id", nullable=False)
        op.create_foreign_key(f"{table}_workspace_id_fkey", table, "assessment_workspaces", ["workspace_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint("uq_blast_events_domain_logical_id", "blast_events", type_="unique")
    op.drop_index("ix_blast_events_domain_id", table_name="blast_events")
    op.create_unique_constraint("uq_blast_events_workspace_domain_id", "blast_events", ["workspace_id", "logical_id"])
    op.create_index("ix_blast_events_workspace_id", "blast_events", ["workspace_id"])
    op.drop_constraint("fk_blast_events_domain_id", "blast_events", type_="foreignkey")
    op.drop_column("blast_events", "domain_id")
    op.drop_constraint("uq_assessment_areas_domain_logical_id", "assessment_areas", type_="unique")
    op.drop_index("ix_assessment_areas_domain_id", table_name="assessment_areas")
    op.create_unique_constraint("uq_assessment_areas_workspace_domain_id", "assessment_areas", ["workspace_id", "logical_id"])
    op.create_index("ix_assessment_areas_workspace_id", "assessment_areas", ["workspace_id"])
    op.drop_constraint("fk_assessment_areas_domain_id", "assessment_areas", type_="foreignkey")
    op.drop_column("assessment_areas", "domain_id")
    # Restore names as well as columns: migration 0006 addresses these exact
    # historical constraint names when continuing toward base.
    for table, old, new in reversed(_CONSTRAINT_RENAMES):
        op.execute(sa.text(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}"))
    for table in _LOGICAL_TABLES + ("blast_events", "assessment_areas"):
        op.alter_column(table, "logical_id", new_column_name="domain_id")
