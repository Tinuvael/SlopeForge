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
    "project_lines_datasets", "blast_events",
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
assert "assessment_workspaces" not in module.Base.metadata.tables
assert module.Base.metadata.tables["blast_events"].c.domain_id is not None
for prefix in ("PySide6", "PyQt6", "ui", "widgets"):
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


def test_canonical_tables_exist_and_retired_parallel_schema_cannot_return():
    assert EXPECTED <= set(Base.metadata.tables)
    retired = {
        "rock_mass_profiles", "rock_structures", "blast_designs",
        "drilling_patterns", "charge_segments", "blast_executions",
        "wall_assessments", "attachments", "explosive_types", "lithologies",
    }
    assert retired.isdisjoint(Base.metadata.tables)
    assert "blast_blocks" in Base.metadata.tables
    assert "mines" in Base.metadata.tables
    assert "assessment_entity_attachments" in Base.metadata.tables
    assert "blast_event_technical_card_revisions" in Base.metadata.tables
    assert "project_lines_datasets" in Base.metadata.tables
    assert {relationship.key for relationship in models.BlastBlock.__mapper__.relationships}.isdisjoint(
        {"rock_mass_profile", "blast_design"}
    )
    assert not EXPECTED.intersection(models.__dict__)


def test_direct_domain_ownership_and_logical_identity():
    assert "assessment_workspaces" not in Base.metadata.tables
    assert ("site_id", "logical_id") in uniques("project_lines_datasets")
    assert ("domain_id", "logical_id") in uniques("blast_events")
    assert ("domain_id", "logical_id") in uniques("assessment_areas")
    assert ("logical_id",) in uniques("assessment_area_evaluations")
    for name in ("blast_events", "assessment_areas"):
        assert table(name).c.domain_id.type.python_type is int
        assert table(name).c.logical_id.type.python_type is str
        assert fk(name, "domain_id").target_fullname == "domains.id"
    assert "domain_id" not in table("project_lines_datasets").c
    assert fk("project_lines_datasets", "site_id").target_fullname == "sites.id"


def test_optional_frozen_link_geometry_uses_sql_null():
    column = table("assessment_event_links").c.frozen_intersection_geometry_json
    assert column.type.none_as_null is True


def test_domain_and_site_scoped_project_lines_foundation():
    assert ("site_id", "name") in uniques("domains")
    assert fk("domains", "site_id").column.table.name == "sites"
    assert fk("project_lines_datasets", "site_id").column.table.name == "sites"
    assert "is_archived" in table("project_lines_datasets").c
    assert "archived_at" in table("project_lines_datasets").c
    assert "NOT (is_archived AND is_active)" in checks("project_lines_datasets")
    assert "site_id" not in table("blast_blocks").c
    assert fk("blast_blocks", "domain_id").column.table.name == "domains"
    assert "is_archived" in table("blast_blocks").c
    assert "archived_at" in table("blast_blocks").c
    assert "horizons" not in Base.metadata.tables


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
        assert (parent, "logical_id") in uniques(name)
        assert (parent, "revision_number") in uniques(name)
        assert "revision_number > 0" in checks(name)
        partial = [i for i in table(name).indexes if i.unique and i.dialect_options["postgresql"]["where"] is not None]
        assert len(partial) == 1
        assert str(partial[0].dialect_options["postgresql"]["where"]) == "is_active"
    dataset_partial = [i for i in table("project_lines_datasets").indexes if i.unique]
    assert len(dataset_partial) == 1
    assert tuple(c.name for c in dataset_partial[0].columns) == ("site_id",)


def test_geometry_elevation_json_and_exact_revision_links():
    geometry = table("assessment_area_geometry_revisions")
    assert "boundary_json" in geometry.c and "selection_polygon_json" not in geometry.c
    assert geometry.c.min_elevation_m.nullable and geometry.c.max_elevation_m.nullable
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
    assert ("logical_id",) in uniques("assessment_entity_attachments")


def test_all_foreign_key_delete_actions():
    expected = {
        ("project_lines_datasets", "site_id"): "RESTRICT",
        ("blast_events", "domain_id"): "RESTRICT",
        ("blast_events", "blast_block_id"): "SET NULL",
        ("blast_event_geometry_revisions", "blast_event_id"): "CASCADE",
        ("blast_event_technical_cards", "blast_event_id"): "CASCADE",
        ("blast_event_technical_card_revisions", "technical_card_id"): "CASCADE",
        ("blast_event_technical_card_revisions", "blast_event_geometry_revision_id"): "RESTRICT",
        ("assessment_areas", "domain_id"): "RESTRICT",
        ("assessment_area_geometry_revisions", "assessment_area_id"): "CASCADE",
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


def test_assessment_schema_keeps_immutable_mvp_baseline():
    versions = sorted(Path("alembic/versions").glob("*.py"))
    assert [path.name for path in versions] == ["0001_mvp_baseline.py", "0002_workflow_status.py"]
    source = versions[0].read_text()
    assert 'revision = "0001_mvp_baseline"' in source
    assert "down_revision = None" in source
    assert "assessment_workspaces" not in source
    for name in EXPECTED:
        assert f"op.create_table('{name}'" in source
        assert f"op.drop_table('{name}')" in source
    for obsolete in (
        "selection_polygon_json", "horizon_slices_json", "lower_elevation_m",
        "upper_elevation_m", "source_dataset_id",
    ):
        assert obsolete not in source
    for current in ("boundary_json", "final_geometry_json", "min_elevation_m", "max_elevation_m"):
        assert current in source
