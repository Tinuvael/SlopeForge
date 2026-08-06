from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import CreateIndex, CreateTable

from database.base import Base
from database import assessment_models, models  # assessment import registers its metadata

EXPECTED = {
    "assessment_workspaces", "project_lines_datasets", "blast_events",
    "blast_event_geometry_revisions", "blast_event_technical_cards",
    "blast_event_technical_card_revisions", "assessment_areas",
    "assessment_area_geometry_revisions", "assessment_event_links",
    "assessment_area_evaluations", "assessment_area_evaluation_revisions",
    "assessment_entity_attachments",
}


def table(name):
    return Base.metadata.tables[name]


def checks(name):
    return " ".join(str(c.sqltext) for c in table(name).constraints if isinstance(c, CheckConstraint))


def uniques(name):
    return {tuple(c.name for c in u.columns) for u in table(name).constraints if isinstance(u, UniqueConstraint)}


def fk(name, column):
    return next(iter(table(name).c[column].foreign_keys))


def test_import_is_declarative_only_in_clean_subprocess():
    code = r'''
import sys
import sqlalchemy
import sqlalchemy.engine

def forbidden(*args, **kwargs):
    raise AssertionError("assessment_models attempted to create an engine or connection")

sqlalchemy.create_engine = forbidden
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.Engine.connect = forbidden
import database.assessment_models as module
assert module.Base.metadata.tables["assessment_workspaces"] is not None
for prefix in ("PySide6", "PyQt6", "ui", "widgets", "prototype_2d"):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules), prefix
'''
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path.cwd())
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_expected_tables_and_legacy_tables_are_unchanged():
    assert EXPECTED <= set(Base.metadata.tables)
    assert models.Attachment.__table__.name == "attachments"
    assert set(models.Attachment.__table__.c.keys()) == {"id", "blast_block_id", "attachment_kind", "subtype", "original_filename", "stored_relative_path", "mime_type", "file_size_bytes", "file_date", "description", "uploaded_by_user_id", "created_at", "updated_at"}
    assert "blast_blocks" in Base.metadata.tables
    assert not EXPECTED.intersection(models.__dict__)


def test_workspace_and_top_level_domain_uniqueness():
    assert ("domain_id",) in uniques("assessment_workspaces")
    assert ("site_id", "domain_id") in uniques("project_lines_datasets")
    assert ("workspace_id", "domain_id") in uniques("blast_events")
    assert ("workspace_id", "domain_id") in uniques("assessment_areas")
    assert ("domain_id",) in uniques("assessment_area_evaluations")
    assert fk("assessment_workspaces", "domain_id").ondelete == "RESTRICT"


def test_blast_event_rules_and_optional_legacy_block_link():
    event = table("blast_events")
    assert event.c.blast_block_id.nullable
    assert fk("blast_events", "blast_block_id").target_fullname == "blast_blocks.id"
    assert fk("blast_events", "blast_block_id").ondelete == "SET NULL"
    assert ("blast_block_id",) in uniques("blast_events")
    sql = checks("blast_events")
    assert "production" in sql and "contour" in sql
    assert "blast_block_id IS NULL OR event_type = 'production'" in sql


def test_revision_identity_numbers_and_active_partial_indexes():
    revisions = {
        "blast_event_geometry_revisions": "blast_event_id",
        "blast_event_technical_card_revisions": "technical_card_id",
        "assessment_area_geometry_revisions": "assessment_area_id",
        "assessment_area_evaluation_revisions": "evaluation_id",
    }
    for name, parent in revisions.items():
        assert (parent, "domain_id") in uniques(name)
        assert (parent, "revision_number") in uniques(name)
        assert "revision_number > 0" in checks(name)
        partial = [i for i in table(name).indexes if i.unique and i.dialect_options["postgresql"]["where"] is not None]
        assert len(partial) == 1
        assert str(partial[0].dialect_options["postgresql"]["where"]) == "is_active"
    dataset_partial = [i for i in table("project_lines_datasets").indexes if i.unique]
    assert len(dataset_partial) == 1
    assert tuple(c.name for c in dataset_partial[0].columns) == ("site_id",)


def test_geometry_elevation_json_and_exact_revision_links():
    assert "lower_elevation_m < upper_elevation_m" in checks("assessment_area_geometry_revisions")
    assert fk("blast_event_technical_card_revisions", "blast_event_geometry_revision_id").target_fullname == "blast_event_geometry_revisions.id"
    assert fk("assessment_area_evaluation_revisions", "assessment_area_geometry_revision_id").target_fullname == "assessment_area_geometry_revisions.id"
    links = table("assessment_event_links")
    assert "blast_event_id" not in links.c
    assert fk("assessment_event_links", "assessment_area_geometry_revision_id").target_fullname == "assessment_area_geometry_revisions.id"
    assert fk("assessment_event_links", "blast_event_geometry_revision_id").target_fullname == "blast_event_geometry_revisions.id"
    for t in EXPECTED:
        for column in table(t).c:
            if column.name.endswith("_json"):
                assert isinstance(column.type, JSONB)


def test_required_domain_fields_are_not_nullable():
    required = {
        "blast_events": ("elevation_m",),
        "blast_event_geometry_revisions": ("elevation_m",),
        "assessment_areas": ("assessment_date",),
        "assessment_entity_attachments": (
            "subtype", "custom_subtype", "title", "file_date", "description",
            "mime_type", "file_size_bytes",
        ),
    }
    for table_name, columns in required.items():
        assert all(not table(table_name).c[column].nullable for column in columns)


def test_attachment_owner_and_other_checks():
    sql = checks("assessment_entity_attachments")
    assert "owner_type = 'blast_event'" in sql
    assert "owner_type = 'assessment_evaluation'" in sql
    assert "file_size_bytes >= 0" in sql
    assert "btrim(relative_path)" in sql
    assert ("domain_id",) in uniques("assessment_entity_attachments")


def test_all_foreign_key_delete_actions():
    expected = {
        ("assessment_workspaces", "domain_id"): "RESTRICT",
        ("project_lines_datasets", "site_id"): "RESTRICT",
        ("blast_events", "workspace_id"): "CASCADE",
        ("blast_events", "blast_block_id"): "SET NULL",
        ("blast_event_geometry_revisions", "blast_event_id"): "CASCADE",
        ("blast_event_technical_cards", "blast_event_id"): "CASCADE",
        ("blast_event_technical_card_revisions", "technical_card_id"): "CASCADE",
        ("blast_event_technical_card_revisions", "blast_event_geometry_revision_id"): "RESTRICT",
        ("assessment_areas", "workspace_id"): "CASCADE",
        ("assessment_area_geometry_revisions", "assessment_area_id"): "CASCADE",
        ("assessment_area_geometry_revisions", "source_dataset_id"): "RESTRICT",
        ("assessment_event_links", "assessment_area_geometry_revision_id"): "CASCADE",
        ("assessment_event_links", "blast_event_geometry_revision_id"): "RESTRICT",
        ("assessment_area_evaluations", "assessment_area_id"): "CASCADE",
        ("assessment_area_evaluation_revisions", "evaluation_id"): "CASCADE",
        ("assessment_area_evaluation_revisions", "assessment_area_geometry_revision_id"): "RESTRICT",
        ("assessment_entity_attachments", "blast_event_id"): "CASCADE",
        ("assessment_entity_attachments", "assessment_area_evaluation_id"): "CASCADE",
    }
    assert {(t, c): fk(t, c).ondelete for t, c in expected} == expected


def test_metadata_and_indexes_compile_with_postgresql():
    dialect = postgresql.dialect()
    for name in EXPECTED:
        assert "CREATE TABLE" in str(CreateTable(table(name)).compile(dialect=dialect))
        for index in table(name).indexes:
            assert "CREATE" in str(CreateIndex(index).compile(dialect=dialect))


def test_new_migration_is_single_schema_only_revision():
    versions = Path("alembic/versions")
    additions = list(versions.glob("*_add_assessment_schema.py"))
    assert len(additions) == 1
    source = additions[0].read_text()
    assert 'down_revision = "20260715_0003"' in source
    for name in EXPECTED:
        assert f"CREATE TABLE {name}" in source
        assert f"op.drop_table('{name}')" in source
    assert not any(line.lstrip().lower().startswith(("insert ", "update ", "delete ")) for line in source.splitlines())
    assert "drop_table('attachments')" not in source
    assert "drop_table('blast_blocks')" not in source
    for ddl in (
        "CONSTRAINT uq_assessment_area_evaluations_domain_id UNIQUE (domain_id)",
        "elevation_m NUMERIC(12, 3) NOT NULL",
        "assessment_date DATE NOT NULL",
        "subtype VARCHAR(80) NOT NULL",
        "custom_subtype VARCHAR(255) NOT NULL",
        "title VARCHAR(255) NOT NULL",
        "file_date DATE NOT NULL",
        "description TEXT NOT NULL",
        "mime_type VARCHAR(255) NOT NULL",
        "file_size_bytes BIGINT NOT NULL",
    ):
        assert ddl in source


def test_nullable_change_reason_correction_migration_matches_orm():
    migration = Path("alembic/versions/20260804_0005_nullable_assessment_area_change_reason.py")
    assert migration.exists()
    source = migration.read_text()
    assert 'revision = "20260804_0005"' in source
    assert 'down_revision = "20260804_0004"' in source
    assert 'alter_column("assessment_area_geometry_revisions", "change_reason", nullable=True)' in source
    update = "UPDATE assessment_area_geometry_revisions SET change_reason = '' WHERE change_reason IS NULL"
    assert update in source
    assert source.index(update) < source.index(
        'alter_column("assessment_area_geometry_revisions", "change_reason", nullable=False)')
    assert table("assessment_area_geometry_revisions").c.change_reason.nullable
