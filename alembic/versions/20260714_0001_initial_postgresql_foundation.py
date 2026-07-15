"""initial PostgreSQL foundation

Revision ID: 20260714_0001
Revises:
Create Date: 2026-07-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260714_0001"
down_revision = None
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("admin", "editor", "viewer", name="user_role", create_type=False)
blast_block_status = postgresql.ENUM("planned", "blasted", "assessed", name="blast_block_status", create_type=False)
structure_type = postgresql.ENUM("joint_set", "tectonic_structure", name="structure_type", create_type=False)
drilling_role = postgresql.ENUM("production", "buffer", "contour", name="drilling_role", create_type=False)
charge_segment_type = postgresql.ENUM("explosive", "stemming", "air_deck", name="charge_segment_type", create_type=False)
wall_rating = postgresql.ENUM("good", "satisfactory", "poor", name="wall_rating", create_type=False)
attachment_kind = postgresql.ENUM("photo", "document", name="attachment_kind", create_type=False)

ENUMS = [user_role, blast_block_status, structure_type, drilling_role, charge_segment_type, wall_rating, attachment_kind]


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "mines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_mines_name", "mines", ["name"])

    op.create_table(
        "lithologies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name", name="uq_lithologies_name"),
    )

    op.create_table(
        "explosive_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name", name="uq_explosive_types_name"),
    )

    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mine_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["mine_id"], ["mines.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_sites_mine_id", "sites", ["mine_id"])
    op.create_index("ix_sites_name", "sites", ["name"])

    op.create_table(
        "blast_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("block_number", sa.String(length=80), nullable=False),
        sa.Column("horizon_m", sa.Numeric(10, 2), nullable=True),
        sa.Column("planned_blast_date", sa.Date(), nullable=True),
        sa.Column("status", blast_block_status, nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_blast_blocks_site_id", "blast_blocks", ["site_id"])
    op.create_index("ix_blast_blocks_created_by_user_id", "blast_blocks", ["created_by_user_id"])
    op.create_index("ix_blast_blocks_status", "blast_blocks", ["status"])
    op.create_index("ix_blast_blocks_site_block_number", "blast_blocks", ["site_id", "block_number"])

    op.create_table(
        "rock_mass_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_block_id", sa.Integer(), nullable=False),
        sa.Column("lithology_id", sa.Integer(), nullable=True),
        sa.Column("rqd_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("rmr", sa.Integer(), nullable=True),
        sa.Column("gsi", sa.Integer(), nullable=True),
        sa.Column("q_value", sa.Numeric(10, 3), nullable=True),
        sa.Column("ucs_mpa", sa.Numeric(10, 3), nullable=True),
        sa.Column("uts_mpa", sa.Numeric(10, 3), nullable=True),
        sa.Column("characteristic_block_size_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["blast_block_id"], ["blast_blocks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lithology_id"], ["lithologies.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("blast_block_id", name="uq_rock_mass_profiles_blast_block_id"),
        sa.CheckConstraint("rqd_percent IS NULL OR (rqd_percent >= 0 AND rqd_percent <= 100)", name="ck_rock_mass_profiles_rqd_percent_range"),
        sa.CheckConstraint("rmr IS NULL OR (rmr >= 0 AND rmr <= 100)", name="ck_rock_mass_profiles_rmr_range"),
        sa.CheckConstraint("gsi IS NULL OR (gsi >= 0 AND gsi <= 100)", name="ck_rock_mass_profiles_gsi_range"),
        sa.CheckConstraint("q_value IS NULL OR q_value > 0", name="ck_rock_mass_profiles_q_value_positive"),
        sa.CheckConstraint("ucs_mpa IS NULL OR ucs_mpa >= 0", name="ck_rock_mass_profiles_ucs_mpa_non_negative"),
        sa.CheckConstraint("uts_mpa IS NULL OR uts_mpa >= 0", name="ck_rock_mass_profiles_uts_mpa_non_negative"),
        sa.CheckConstraint("characteristic_block_size_m IS NULL OR characteristic_block_size_m >= 0", name="ck_rock_mass_profiles_block_size_non_negative"),
    )
    op.create_index("ix_rock_mass_profiles_lithology_id", "rock_mass_profiles", ["lithology_id"])

    op.create_table(
        "rock_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rock_mass_profile_id", sa.Integer(), nullable=False),
        sa.Column("structure_type", structure_type, nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("dip_deg", sa.Numeric(5, 2), nullable=True),
        sa.Column("dip_direction_deg", sa.Numeric(6, 2), nullable=True),
        sa.Column("thickness_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["rock_mass_profile_id"], ["rock_mass_profiles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("rock_mass_profile_id", "structure_type", "sequence_number", name="uq_rock_structures_profile_type_sequence"),
        sa.CheckConstraint("dip_deg IS NULL OR (dip_deg >= 0 AND dip_deg <= 90)", name="ck_rock_structures_dip_deg_range"),
        sa.CheckConstraint("dip_direction_deg IS NULL OR (dip_direction_deg >= 0 AND dip_direction_deg < 360)", name="ck_rock_structures_dip_direction_deg_range"),
        sa.CheckConstraint("thickness_m IS NULL OR thickness_m >= 0", name="ck_rock_structures_thickness_m_non_negative"),
        sa.CheckConstraint("sequence_number >= 1 AND sequence_number <= 5", name="ck_rock_structures_sequence_number_range"),
    )
    op.create_index("ix_rock_structures_rock_mass_profile_id", "rock_structures", ["rock_mass_profile_id"])

    op.create_table(
        "blast_designs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_block_id", sa.Integer(), nullable=False),
        sa.Column("contour_drilling", sa.Boolean(), nullable=True),
        sa.Column("specific_explosive_consumption_kg_m3", sa.Numeric(10, 4), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["blast_block_id"], ["blast_blocks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("blast_block_id", name="uq_blast_designs_blast_block_id"),
        sa.CheckConstraint("specific_explosive_consumption_kg_m3 IS NULL OR specific_explosive_consumption_kg_m3 >= 0", name="ck_blast_designs_sec_non_negative"),
    )

    op.create_table(
        "drilling_patterns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_design_id", sa.Integer(), nullable=False),
        sa.Column("drilling_role", drilling_role, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("diameter_mm", sa.Numeric(10, 3), nullable=True),
        sa.Column("spacing_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("burden_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("depth_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("toe_offset_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("explosive_type_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["blast_design_id"], ["blast_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["explosive_type_id"], ["explosive_types.id"], ondelete="SET NULL"),
        sa.CheckConstraint("diameter_mm IS NULL OR diameter_mm >= 0", name="ck_drilling_patterns_diameter_mm_non_negative"),
        sa.CheckConstraint("spacing_m IS NULL OR spacing_m >= 0", name="ck_drilling_patterns_spacing_m_non_negative"),
        sa.CheckConstraint("burden_m IS NULL OR burden_m >= 0", name="ck_drilling_patterns_burden_m_non_negative"),
        sa.CheckConstraint("depth_m IS NULL OR depth_m >= 0", name="ck_drilling_patterns_depth_m_non_negative"),
        sa.CheckConstraint("toe_offset_m IS NULL OR toe_offset_m >= 0", name="ck_drilling_patterns_toe_offset_m_non_negative"),
    )
    op.create_index("ix_drilling_patterns_blast_design_id", "drilling_patterns", ["blast_design_id"])
    op.create_index("ix_drilling_patterns_drilling_role", "drilling_patterns", ["drilling_role"])
    op.create_index("ix_drilling_patterns_explosive_type_id", "drilling_patterns", ["explosive_type_id"])

    op.create_table(
        "charge_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drilling_pattern_id", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("segment_type", charge_segment_type, nullable=False),
        sa.Column("length_m", sa.Numeric(10, 3), nullable=False),
        sa.Column("explosive_type_id", sa.Integer(), nullable=True),
        sa.Column("charge_mass_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["drilling_pattern_id"], ["drilling_patterns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["explosive_type_id"], ["explosive_types.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("drilling_pattern_id", "sequence_number", name="uq_charge_segments_pattern_sequence"),
        sa.CheckConstraint("length_m > 0", name="ck_charge_segments_length_m_positive"),
        sa.CheckConstraint("charge_mass_kg IS NULL OR charge_mass_kg >= 0", name="ck_charge_segments_charge_mass_kg_non_negative"),
        sa.CheckConstraint("sequence_number > 0", name="ck_charge_segments_sequence_number_positive"),
    )
    op.create_index("ix_charge_segments_drilling_pattern_id", "charge_segments", ["drilling_pattern_id"])
    op.create_index("ix_charge_segments_explosive_type_id", "charge_segments", ["explosive_type_id"])

    op.create_table(
        "blast_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_block_id", sa.Integer(), nullable=False),
        sa.Column("actual_blast_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiation_description", sa.Text(), nullable=True),
        sa.Column("weather_conditions", sa.Text(), nullable=True),
        sa.Column("actual_explosive_consumption_kg_m3", sa.Numeric(10, 4), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["blast_block_id"], ["blast_blocks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("blast_block_id", name="uq_blast_executions_blast_block_id"),
        sa.CheckConstraint("actual_explosive_consumption_kg_m3 IS NULL OR actual_explosive_consumption_kg_m3 >= 0", name="ck_blast_executions_sec_non_negative"),
    )

    op.create_table(
        "wall_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_block_id", sa.Integer(), nullable=False),
        sa.Column("rms_deviation_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("mean_deviation_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("max_overbreak_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("max_underbreak_m", sa.Numeric(10, 3), nullable=True),
        sa.Column("assessment_matrix_name", sa.String(length=255), nullable=True),
        sa.Column("assessment_matrix_score", sa.Numeric(10, 3), nullable=True),
        sa.Column("rating", wall_rating, nullable=True),
        sa.Column("engineer_comment", sa.Text(), nullable=True),
        sa.Column("assessed_by_user_id", sa.Integer(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["blast_block_id"], ["blast_blocks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("blast_block_id", name="uq_wall_assessments_blast_block_id"),
    )
    op.create_index("ix_wall_assessments_rating", "wall_assessments", ["rating"])
    op.create_index("ix_wall_assessments_assessed_by_user_id", "wall_assessments", ["assessed_by_user_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blast_block_id", sa.Integer(), nullable=False),
        sa.Column("attachment_kind", attachment_kind, nullable=False),
        sa.Column("subtype", sa.String(length=80), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_relative_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("file_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["blast_block_id"], ["blast_blocks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("stored_relative_path", name="uq_attachments_stored_relative_path"),
        sa.CheckConstraint("file_size_bytes IS NULL OR file_size_bytes >= 0", name="ck_attachments_file_size_bytes_non_negative"),
        sa.CheckConstraint("attachment_kind <> 'photo' OR subtype IN ('before_blast', 'after_blast', 'drilling', 'final_wall', 'other')", name="ck_attachments_photo_subtype"),
    )
    op.create_index("ix_attachments_blast_block_id", "attachments", ["blast_block_id"])
    op.create_index("ix_attachments_attachment_kind", "attachments", ["attachment_kind"])
    op.create_index("ix_attachments_uploaded_by_user_id", "attachments", ["uploaded_by_user_id"])


def downgrade() -> None:
    for table_name in [
        "attachments",
        "wall_assessments",
        "blast_executions",
        "charge_segments",
        "drilling_patterns",
        "blast_designs",
        "rock_structures",
        "rock_mass_profiles",
        "blast_blocks",
        "sites",
        "explosive_types",
        "lithologies",
        "mines",
        "users",
    ]:
        op.drop_table(table_name)

    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)
