from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def _require_destructive_test_database(url: str) -> None:
    """Keep migration resets away from development and production databases."""
    if "test" not in (make_url(url).database or "").lower():
        pytest.fail("Refusing migration test outside a test database", pytrace=False)


def _alembic_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, url: str):
    from alembic.config import Config

    _require_destructive_test_database(url)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    return Config("alembic.ini")


def test_destructive_migration_guard_rejects_non_test_database() -> None:
    with pytest.raises(pytest.fail.Exception, match="outside a test database"):
        _require_destructive_test_database(
            "postgresql+psycopg://slopeforge@localhost:5432/slopeforge"
        )


def test_mvp_baseline_is_the_only_alembic_head() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["0001_mvp_baseline"]
    assert [revision.revision for revision in script.walk_revisions()] == [
        "0001_mvp_baseline"
    ]


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_mvp_baseline_upgrade_schema_smoke_and_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Build only the baseline, exercise the stacked schema, then base -> head."""
    from alembic import command

    url = os.environ["TEST_DATABASE_URL"]
    config = _alembic_config(monkeypatch, tmp_path, url)
    engine = create_engine(url)
    boundary = {
        "segments": [
            {
                "type": "project_line_span",
                "dataset_logical_id": "LINES-1",
                "source_line_id": "crest-1",
                "start_fraction": 0.0,
                "end_fraction": 1.0,
                "frozen_points": [[0, 0, 110], [10, 0, 105]],
            },
            {
                "type": "straight_connector",
                "start": [10, 0, 105],
                "end": [0, 0, 110],
            },
        ]
    }
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        with engine.begin() as connection:
            mine_id = connection.scalar(text("INSERT INTO mines (name) VALUES ('MVP') RETURNING id"))
            site_id = connection.scalar(text("INSERT INTO sites (mine_id, name) VALUES (:m, 'Project') RETURNING id"), {"m": mine_id})
            domain_id = connection.scalar(text("INSERT INTO domains (site_id, name) VALUES (:s, 'North') RETURNING id"), {"s": site_id})
            connection.execute(text("""INSERT INTO project_lines_datasets
                (site_id, logical_id, name, imported_at, source_file_name, is_active, is_archived, lines_json)
                VALUES (:site, 'LINES-1', 'Survey', now(), 'survey.csv', true, false,
                        CAST(:lines AS jsonb))"""), {"site": site_id, "lines": '[{"id":"crest-1","points":[[0,0,110],[10,0,105]]}]'})
            block_id = connection.scalar(text("""INSERT INTO blast_blocks
                (domain_id, block_number, status, is_archived)
                VALUES (:domain, 'B-1', 'planned', false) RETURNING id"""), {"domain": domain_id})
            connection.execute(text("""INSERT INTO blast_events
                (domain_id, logical_id, name, event_type, elevation_m, blast_block_id, is_archived)
                VALUES (:domain, 'PROD-1', 'Production', 'production', 100, :block, false),
                       (:domain, 'CONT-1', 'Contour', 'contour', 105, NULL, false)"""), {"domain": domain_id, "block": block_id})
            area_id = connection.scalar(text("""INSERT INTO assessment_areas
                (domain_id, logical_id, name, assessment_date, is_archived)
                VALUES (:domain, 'AREA-1', 'North wall', CURRENT_DATE, false) RETURNING id"""), {"domain": domain_id})
            connection.execute(text("""INSERT INTO assessment_area_geometry_revisions
                (assessment_area_id, logical_id, revision_number, created_at, boundary_json,
                 final_geometry_json, min_elevation_m, max_elevation_m, change_reason, is_active)
                VALUES (:area, 'GEOM-1', 1, now(), CAST(:boundary AS jsonb),
                        '{"type":"Polygon","coordinates":[[[0,0],[10,0],[0,0]]]}'::jsonb,
                        NULL, 110, 'Initial traced boundary', true)"""), {"area": area_id, "boundary": __import__("json").dumps(boundary)})
        with engine.connect() as connection:
            row = connection.execute(text("""SELECT r.boundary_json, r.final_geometry_json,
                r.min_elevation_m, r.max_elevation_m
                FROM assessment_area_geometry_revisions r
                JOIN assessment_areas a ON a.id=r.assessment_area_id
                WHERE a.logical_id='AREA-1'""")).one()
            assert [segment["type"] for segment in row.boundary_json["segments"]] == [
                "project_line_span", "straight_connector"
            ]
            assert row.final_geometry_json["type"] == "Polygon"
            assert row.min_elevation_m is None
            assert float(row.max_elevation_m) == 110
            assert connection.scalar(text("SELECT count(*) FROM blast_events")) == 2

        # The initial baseline must be fully reversible and repeatable.
        command.downgrade(config, "base")
        assert "users" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        assert set(inspect(engine).get_table_names()) >= {
            "users", "sites", "domains", "blast_events", "blast_blocks",
            "project_lines_datasets", "assessment_areas",
            "assessment_area_geometry_revisions", "assessment_event_links",
        }
    finally:
        engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_fresh_baseline_matches_application_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Compare application-relevant tables, columns, keys, checks, and indexes."""
    from alembic import command
    from database.base import Base
    import database.assessment_models  # noqa: F401
    import database.models  # noqa: F401

    url = os.environ["TEST_DATABASE_URL"]
    config = _alembic_config(monkeypatch, tmp_path, url)
    engine = create_engine(url)
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= set(Base.metadata.tables)
        for name, model_table in Base.metadata.tables.items():
            actual_columns = {column["name"]: column for column in inspector.get_columns(name)}
            assert set(actual_columns) == set(model_table.columns), name
            for column in model_table.columns:
                assert actual_columns[column.name]["nullable"] == column.nullable, f"{name}.{column.name}"
            assert set(inspector.get_pk_constraint(name)["constrained_columns"]) == set(model_table.primary_key.columns.keys())
            actual_fks = {
                (tuple(fk["constrained_columns"]), tuple(fk["referred_columns"]), fk["referred_table"])
                for fk in inspector.get_foreign_keys(name)
            }
            expected_fks = {
                (tuple(fk.parent.name for fk in constraint.elements),
                 tuple(fk.column.name for fk in constraint.elements),
                 constraint.elements[0].column.table.name)
                for constraint in model_table.foreign_key_constraints
            }
            assert actual_fks == expected_fks, name
            actual_indexes = {index["name"] for index in inspector.get_indexes(name)}
            assert {index.name for index in model_table.indexes} <= actual_indexes
            actual_checks = {check["name"] for check in inspector.get_check_constraints(name)}
            assert {check.name for check in model_table.constraints if check.__class__.__name__ == "CheckConstraint"} <= actual_checks
    finally:
        engine.dispose()
