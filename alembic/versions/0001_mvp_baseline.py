"""Canonical PostgreSQL schema for the pre-production MVP.

This baseline intentionally replaces the disposable development migration history.
Future schema changes must be added as new migrations rather than editing this file.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_mvp_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('mines',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mines_name'), 'mines', ['name'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('role', sa.Enum('admin', 'editor', 'viewer', name='user_role'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_created_by_user_id'), 'users', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_users_updated_by_user_id'), 'users', ['updated_by_user_id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('remember_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=128), nullable=False),
    sa.Column('device_name', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_remember_tokens_expires_at'), 'remember_tokens', ['expires_at'], unique=False)
    op.create_index(op.f('ix_remember_tokens_revoked_at'), 'remember_tokens', ['revoked_at'], unique=False)
    op.create_index(op.f('ix_remember_tokens_token_hash'), 'remember_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_remember_tokens_user_id'), 'remember_tokens', ['user_id'], unique=False)
    op.create_table('sites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mine_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['mine_id'], ['mines.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sites_mine_id'), 'sites', ['mine_id'], unique=False)
    op.create_index(op.f('ix_sites_name'), 'sites', ['name'], unique=False)
    op.create_table('domains',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('site_id', 'name', name='uq_domains_site_name')
    )
    op.create_index(op.f('ix_domains_site_id'), 'domains', ['site_id'], unique=False)
    op.create_table('project_lines_datasets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('source_file_name', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lines_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.CheckConstraint("jsonb_typeof(lines_json) = 'array'", name='ck_project_lines_datasets_lines_json_array'),
    sa.CheckConstraint('NOT (is_archived AND is_active)', name='ck_project_lines_datasets_archived_not_active'),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('site_id', 'logical_id', name='uq_project_lines_datasets_site_logical_id')
    )
    op.create_index('ix_project_lines_datasets_imported_at', 'project_lines_datasets', ['imported_at'], unique=False)
    op.create_index('ix_project_lines_datasets_one_active_per_site', 'project_lines_datasets', ['site_id'], unique=True, postgresql_where=sa.text('is_active'))
    op.create_index('ix_project_lines_datasets_site_id', 'project_lines_datasets', ['site_id'], unique=False)
    op.create_table('assessment_areas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('domain_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('assessment_date', sa.Date(), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('archive_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('domain_id', 'logical_id', name='uq_assessment_areas_domain_logical_id')
    )
    op.create_index('ix_assessment_areas_assessment_date', 'assessment_areas', ['assessment_date'], unique=False)
    op.create_index('ix_assessment_areas_domain_id', 'assessment_areas', ['domain_id'], unique=False)
    op.create_index('ix_assessment_areas_is_archived', 'assessment_areas', ['is_archived'], unique=False)
    op.create_table('blast_blocks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('domain_id', sa.Integer(), nullable=False),
    sa.Column('block_number', sa.String(length=80), nullable=False),
    sa.Column('horizon_m', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('planned_blast_date', sa.Date(), nullable=True),
    sa.Column('status', sa.Enum('planned', 'blasted', 'assessed', name='blast_block_status'), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blast_blocks_created_by_user_id'), 'blast_blocks', ['created_by_user_id'], unique=False)
    op.create_index('ix_blast_blocks_domain_block_number', 'blast_blocks', ['domain_id', 'block_number'], unique=False)
    op.create_index(op.f('ix_blast_blocks_domain_id'), 'blast_blocks', ['domain_id'], unique=False)
    op.create_index(op.f('ix_blast_blocks_is_archived'), 'blast_blocks', ['is_archived'], unique=False)
    op.create_index(op.f('ix_blast_blocks_status'), 'blast_blocks', ['status'], unique=False)
    op.create_table('domain_geometries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('domain_id', sa.Integer(), nullable=False),
    sa.Column('polygons_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.Column('source_kind', sa.String(length=20), nullable=False),
    sa.Column('source_file_name', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("jsonb_typeof(polygons_json) = 'array'", name='ck_domain_geometries_polygons_array'),
    sa.CheckConstraint("source_kind IN ('imported', 'drawn')", name='ck_domain_geometries_source_kind'),
    sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('domain_id', name='uq_domain_geometries_domain_id')
    )
    op.create_index(op.f('ix_domain_geometries_domain_id'), 'domain_geometries', ['domain_id'], unique=False)
    op.create_table('assessment_area_evaluations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('assessment_area_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assessment_area_id'], ['assessment_areas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('assessment_area_id', name='uq_assessment_area_evaluations_area'),
    sa.UniqueConstraint('logical_id', name='uq_assessment_area_evaluations_logical_id')
    )
    op.create_table('assessment_area_geometry_revisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('assessment_area_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('revision_number', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('boundary_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.Column('final_geometry_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.Column('min_elevation_m', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('max_elevation_m', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('change_reason', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.CheckConstraint("jsonb_typeof(boundary_json) = 'object'", name='ck_assessment_area_geometry_revisions_boundary_object'),
    sa.CheckConstraint("jsonb_typeof(final_geometry_json) = 'object'", name='ck_assessment_area_geometry_revisions_final_object'),
    sa.CheckConstraint('revision_number > 0', name='ck_assessment_area_geometry_revisions_number_positive'),
    sa.ForeignKeyConstraint(['assessment_area_id'], ['assessment_areas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('assessment_area_id', 'logical_id', name='uq_assessment_area_geometry_revisions_parent_logical_id'),
    sa.UniqueConstraint('assessment_area_id', 'revision_number', name='uq_assessment_area_geometry_revisions_parent_number')
    )
    op.create_index('ix_assessment_area_geometry_revisions_one_active', 'assessment_area_geometry_revisions', ['assessment_area_id'], unique=True, postgresql_where=sa.text('is_active'))
    op.create_table('audit_log_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('blast_block_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('entity_type', sa.String(length=80), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('field_name', sa.String(length=80), nullable=True),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action IN ('create', 'update', 'delete', 'attach', 'detach')", name='ck_audit_log_entries_action'),
    sa.CheckConstraint("entity_type IN ('blast_block', 'attachment', 'rock_mass_profile', 'rock_structure', 'blast_design', 'drilling_pattern', 'wall_assessment')", name='ck_audit_log_entries_entity_type'),
    sa.ForeignKeyConstraint(['blast_block_id'], ['blast_blocks.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_entries_action'), 'audit_log_entries', ['action'], unique=False)
    op.create_index(op.f('ix_audit_log_entries_blast_block_id'), 'audit_log_entries', ['blast_block_id'], unique=False)
    op.create_index(op.f('ix_audit_log_entries_created_at'), 'audit_log_entries', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_log_entries_user_id'), 'audit_log_entries', ['user_id'], unique=False)
    op.create_table('blast_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('domain_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=True),
    sa.Column('elevation_m', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('blast_block_id', sa.Integer(), nullable=True),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('archive_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("blast_block_id IS NULL OR event_type = 'production'", name='ck_blast_events_block_production_only'),
    sa.CheckConstraint("event_type IN ('production', 'contour')", name='ck_blast_events_event_type'),
    sa.ForeignKeyConstraint(['blast_block_id'], ['blast_blocks.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('blast_block_id', name='uq_blast_events_blast_block_id'),
    sa.UniqueConstraint('domain_id', 'logical_id', name='uq_blast_events_domain_logical_id')
    )
    op.create_index('ix_blast_events_domain_id', 'blast_events', ['domain_id'], unique=False)
    op.create_index('ix_blast_events_elevation_m', 'blast_events', ['elevation_m'], unique=False)
    op.create_index('ix_blast_events_event_date', 'blast_events', ['event_date'], unique=False)
    op.create_index('ix_blast_events_event_type', 'blast_events', ['event_type'], unique=False)
    op.create_index('ix_blast_events_is_archived', 'blast_events', ['is_archived'], unique=False)
    op.create_table('assessment_area_evaluation_revisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('evaluation_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('revision_number', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('assessment_area_geometry_revision_id', sa.Integer(), nullable=False),
    sa.Column('assessment_date', sa.Date(), nullable=True),
    sa.Column('inspector', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('matrix_template_id', sa.String(length=255), nullable=False),
    sa.Column('matrix_template_version', sa.Integer(), nullable=False),
    sa.Column('design_achievement_index', sa.Numeric(precision=8, scale=6), nullable=True),
    sa.Column('face_condition_index', sa.Numeric(precision=8, scale=6), nullable=True),
    sa.Column('result_quadrant', sa.String(length=80), nullable=True),
    sa.Column('payload_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.CheckConstraint("jsonb_typeof(payload_json) = 'object'", name='ck_assessment_evaluation_revisions_payload_object'),
    sa.CheckConstraint("status IN ('draft', 'completed')", name='ck_assessment_evaluation_revisions_status'),
    sa.CheckConstraint('design_achievement_index IS NULL OR design_achievement_index BETWEEN 0 AND 1', name='ck_assessment_evaluation_revisions_design_index'),
    sa.CheckConstraint('face_condition_index IS NULL OR face_condition_index BETWEEN 0 AND 1', name='ck_assessment_evaluation_revisions_face_index'),
    sa.CheckConstraint('matrix_template_version > 0', name='ck_assessment_evaluation_revisions_template_version_positive'),
    sa.CheckConstraint('revision_number > 0', name='ck_assessment_evaluation_revisions_number_positive'),
    sa.ForeignKeyConstraint(['assessment_area_geometry_revision_id'], ['assessment_area_geometry_revisions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['evaluation_id'], ['assessment_area_evaluations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('evaluation_id', 'logical_id', name='uq_assessment_evaluation_revisions_parent_logical_id'),
    sa.UniqueConstraint('evaluation_id', 'revision_number', name='uq_assessment_evaluation_revisions_parent_number')
    )
    op.create_index('ix_assessment_evaluation_revisions_one_active', 'assessment_area_evaluation_revisions', ['evaluation_id'], unique=True, postgresql_where=sa.text('is_active'))
    op.create_table('assessment_entity_attachments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('owner_type', sa.String(length=30), nullable=False),
    sa.Column('blast_event_id', sa.Integer(), nullable=True),
    sa.Column('assessment_area_evaluation_id', sa.Integer(), nullable=True),
    sa.Column('attachment_kind', sa.String(length=20), nullable=False),
    sa.Column('subtype', sa.String(length=80), nullable=False),
    sa.Column('custom_subtype', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('stored_filename', sa.String(length=255), nullable=False),
    sa.Column('relative_path', sa.String(length=1024), nullable=False),
    sa.Column('file_date', sa.Date(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('mime_type', sa.String(length=255), nullable=False),
    sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(owner_type = 'blast_event' AND blast_event_id IS NOT NULL AND assessment_area_evaluation_id IS NULL) OR (owner_type = 'assessment_evaluation' AND assessment_area_evaluation_id IS NOT NULL AND blast_event_id IS NULL)", name='ck_assessment_entity_attachments_owner'),
    sa.CheckConstraint("attachment_kind IN ('photo', 'document')", name='ck_assessment_entity_attachments_kind'),
    sa.CheckConstraint('file_size_bytes IS NULL OR file_size_bytes >= 0', name='ck_assessment_entity_attachments_file_size'),
    sa.CheckConstraint('length(btrim(relative_path)) > 0', name='ck_assessment_entity_attachments_relative_path'),
    sa.ForeignKeyConstraint(['assessment_area_evaluation_id'], ['assessment_area_evaluations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['blast_event_id'], ['blast_events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('logical_id', name='uq_assessment_entity_attachments_logical_id')
    )
    op.create_index('ix_assessment_entity_attachments_blast_event_id', 'assessment_entity_attachments', ['blast_event_id'], unique=False)
    op.create_index('ix_assessment_entity_attachments_evaluation_id', 'assessment_entity_attachments', ['assessment_area_evaluation_id'], unique=False)
    op.create_index('ix_assessment_entity_attachments_file_date', 'assessment_entity_attachments', ['file_date'], unique=False)
    op.create_index('ix_assessment_entity_attachments_kind', 'assessment_entity_attachments', ['attachment_kind'], unique=False)
    op.create_table('blast_event_geometry_revisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('blast_event_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('revision_number', sa.Integer(), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('source_file_name', sa.String(length=255), nullable=False),
    sa.Column('source_geometry_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.Column('plan_geometry_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.Column('elevation_m', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.CheckConstraint("jsonb_typeof(plan_geometry_json) = 'object'", name='ck_blast_event_geometry_revisions_plan_object'),
    sa.CheckConstraint("jsonb_typeof(source_geometry_json) = 'array'", name='ck_blast_event_geometry_revisions_source_array'),
    sa.CheckConstraint('revision_number > 0', name='ck_blast_event_geometry_revisions_number_positive'),
    sa.ForeignKeyConstraint(['blast_event_id'], ['blast_events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('blast_event_id', 'logical_id', name='uq_blast_event_geometry_revisions_parent_logical_id'),
    sa.UniqueConstraint('blast_event_id', 'revision_number', name='uq_blast_event_geometry_revisions_parent_number')
    )
    op.create_index('ix_blast_event_geometry_revisions_one_active', 'blast_event_geometry_revisions', ['blast_event_id'], unique=True, postgresql_where=sa.text('is_active'))
    op.create_table('blast_event_technical_cards',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('blast_event_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['blast_event_id'], ['blast_events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('blast_event_id', name='uq_blast_event_technical_cards_event'),
    sa.UniqueConstraint('logical_id', name='uq_blast_event_technical_cards_logical_id')
    )
    op.create_table('assessment_event_links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('assessment_area_geometry_revision_id', sa.Integer(), nullable=False),
    sa.Column('blast_event_geometry_revision_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('frozen_intersection_geometry_json', postgresql.JSONB(none_as_null=True, astext_type=Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("frozen_intersection_geometry_json IS NULL OR jsonb_typeof(frozen_intersection_geometry_json) = 'object'", name='ck_assessment_event_links_frozen_object'),
    sa.CheckConstraint("source IN ('automatic', 'manual')", name='ck_assessment_event_links_source'),
    sa.CheckConstraint("status IN ('suggested', 'confirmed', 'excluded')", name='ck_assessment_event_links_status'),
    sa.ForeignKeyConstraint(['assessment_area_geometry_revision_id'], ['assessment_area_geometry_revisions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['blast_event_geometry_revision_id'], ['blast_event_geometry_revisions.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('assessment_area_geometry_revision_id', 'blast_event_geometry_revision_id', 'source', name='uq_assessment_event_links_geometry_source'),
    sa.UniqueConstraint('assessment_area_geometry_revision_id', 'logical_id', name='uq_assessment_event_links_parent_logical_id')
    )
    op.create_index('ix_assessment_event_links_area_geometry_revision_id', 'assessment_event_links', ['assessment_area_geometry_revision_id'], unique=False)
    op.create_index('ix_assessment_event_links_blast_geometry_revision_id', 'assessment_event_links', ['blast_event_geometry_revision_id'], unique=False)
    op.create_index('ix_assessment_event_links_status', 'assessment_event_links', ['status'], unique=False)
    op.create_table('blast_event_technical_card_revisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('technical_card_id', sa.Integer(), nullable=False),
    sa.Column('logical_id', sa.String(length=255), nullable=False),
    sa.Column('revision_number', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('blast_event_geometry_revision_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('author', sa.String(length=255), nullable=True),
    sa.Column('change_reason', sa.Text(), nullable=False),
    sa.Column('payload_json', postgresql.JSONB(astext_type=Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.CheckConstraint("event_type IN ('production', 'contour')", name='ck_technical_card_revisions_event_type'),
    sa.CheckConstraint("jsonb_typeof(payload_json) = 'object'", name='ck_technical_card_revisions_payload_object'),
    sa.CheckConstraint("status IN ('draft', 'completed')", name='ck_technical_card_revisions_status'),
    sa.CheckConstraint('revision_number > 0', name='ck_technical_card_revisions_number_positive'),
    sa.ForeignKeyConstraint(['blast_event_geometry_revision_id'], ['blast_event_geometry_revisions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['technical_card_id'], ['blast_event_technical_cards.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('technical_card_id', 'logical_id', name='uq_technical_card_revisions_parent_logical_id'),
    sa.UniqueConstraint('technical_card_id', 'revision_number', name='uq_technical_card_revisions_parent_number')
    )
    op.create_index('ix_technical_card_revisions_one_active', 'blast_event_technical_card_revisions', ['technical_card_id'], unique=True, postgresql_where=sa.text('is_active'))



def downgrade() -> None:
    op.drop_table('blast_event_technical_card_revisions')
    op.drop_table('assessment_event_links')
    op.drop_table('blast_event_technical_cards')
    op.drop_table('blast_event_geometry_revisions')
    op.drop_table('assessment_entity_attachments')
    op.drop_table('assessment_area_evaluation_revisions')
    op.drop_table('blast_events')
    op.drop_table('audit_log_entries')
    op.drop_table('assessment_area_geometry_revisions')
    op.drop_table('assessment_area_evaluations')
    op.drop_table('domain_geometries')
    op.drop_table('blast_blocks')
    op.drop_table('assessment_areas')
    op.drop_table('project_lines_datasets')
    op.drop_table('domains')
    op.drop_table('sites')
    op.drop_table('remember_tokens')
    op.drop_table('users')
    op.drop_table('mines')
    # Native PostgreSQL enum types outlive their tables unless removed explicitly.
    sa.Enum(name="blast_block_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
