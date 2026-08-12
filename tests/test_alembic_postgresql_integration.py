from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_0010_preserves_ids_and_restores_full_downgrade_history(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Exercise the Phase 6A boundary itself, then continue through old history."""
    url = os.environ["TEST_DATABASE_URL"]
    if "test" not in (make_url(url).database or "").lower():
        pytest.fail("Refusing migration test outside a test database", pytrace=False)
    from alembic import command
    from alembic.config import Config
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage-0010"))
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "20260812_0009")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            mine = connection.scalar(text("INSERT INTO mines (name) VALUES ('phase6a') RETURNING id"))
            site = connection.scalar(text(
                "INSERT INTO sites (mine_id, name) VALUES (:m, 'phase6a') RETURNING id"), {"m": mine})
            domain = connection.scalar(text(
                "INSERT INTO domains (site_id, name) VALUES (:s, 'North') RETURNING id"), {"s": site})
            workspace = connection.scalar(text(
                "INSERT INTO assessment_workspaces (domain_id) VALUES (:d) RETURNING id"), {"d": domain})
            dataset = connection.scalar(text("""INSERT INTO project_lines_datasets
                (site_id, domain_id, name, imported_at, source_file_name, is_active, is_archived, lines_json)
                VALUES (:s, 'LINES-1', 'Lines', now(), 'lines.csv', true, false, '[]'::jsonb)
                RETURNING id"""), {"s": site})
            event = connection.scalar(text("""INSERT INTO blast_events
                (workspace_id, domain_id, name, event_type, elevation_m, is_archived)
                VALUES (:w, 'EVENT-1', 'Event', 'contour', 100, false) RETURNING id"""), {"w": workspace})
            area = connection.scalar(text("""INSERT INTO assessment_areas
                (workspace_id, domain_id, name, assessment_date, is_archived)
                VALUES (:w, 'AREA-1', 'Area', CURRENT_DATE, false) RETURNING id"""), {"w": workspace})
        command.upgrade(config, "20260812_0010")
        with engine.connect() as connection:
            assert not connection.scalar(text("SELECT to_regclass('assessment_workspaces') IS NOT NULL"))
            assert connection.execute(text(
                "SELECT domain_id, logical_id FROM blast_events WHERE id=:id"), {"id": event}).one() == (domain, "EVENT-1")
            assert connection.execute(text(
                "SELECT domain_id, logical_id FROM assessment_areas WHERE id=:id"), {"id": area}).one() == (domain, "AREA-1")
            assert connection.scalar(text(
                "SELECT logical_id FROM project_lines_datasets WHERE id=:id"), {"id": dataset}) == "LINES-1"
            assert connection.scalar(text("""SELECT count(*) FROM information_schema.table_constraints
                WHERE table_name IN ('blast_events','assessment_areas')
                  AND constraint_type='FOREIGN KEY' AND constraint_name IN
                  ('fk_blast_events_domain_id','fk_assessment_areas_domain_id')""")) == 2
        command.downgrade(config, "20260812_0009")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT to_regclass('assessment_workspaces') IS NOT NULL"))
            restored_event = connection.execute(text(
                "SELECT workspace_id, domain_id FROM blast_events WHERE id=:id"), {"id": event}).one()
            restored_area = connection.execute(text(
                "SELECT workspace_id, domain_id FROM assessment_areas WHERE id=:id"), {"id": area}).one()
            assert restored_event[0] == restored_area[0]
            assert connection.scalar(text(
                "SELECT domain_id FROM assessment_workspaces WHERE id=:id"),
                {"id": restored_event[0]}) == domain
            assert restored_event[1] == "EVENT-1" and restored_area[1] == "AREA-1"
            expected = {
                "fk_assessment_workspaces_domain_id", "uq_assessment_workspaces_domain_id",
                "uq_project_lines_datasets_site_domain_id",
                "uq_blast_events_workspace_domain_id", "uq_assessment_areas_workspace_domain_id",
            }
            names = set(connection.scalars(text(
                "SELECT conname FROM pg_constraint WHERE conname = ANY(:names)"), {"names": list(expected)}))
            assert names == expected
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        from alembic.script import ScriptDirectory
        assert len(ScriptDirectory.from_config(config).get_heads()) == 1
    finally:
        engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_0009_backfills_non_null_domain_version_and_round_trips(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = os.environ["TEST_DATABASE_URL"]
    if "test" not in (make_url(url).database or "").lower():
        pytest.fail("Refusing migration test outside a test database", pytrace=False)
    from alembic import command
    from alembic.config import Config
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage-0009"))
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "20260809_0008")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            mine = connection.scalar(text("INSERT INTO mines (name) VALUES ('v9') RETURNING id"))
            site = connection.scalar(text(
                "INSERT INTO sites (mine_id, name) VALUES (:mine, 'v9') RETURNING id"),
                {"mine": mine})
            domain = connection.scalar(text(
                "INSERT INTO domains (site_id, name) VALUES (:site, 'v9') RETURNING id"),
                {"site": site})
        command.upgrade(config, "20260812_0009")
        with engine.connect() as connection:
            assert connection.scalar(text(
                "SELECT version FROM domains WHERE id=:id"), {"id": domain}) == 0
            assert connection.scalar(text("""
                SELECT is_nullable FROM information_schema.columns
                WHERE table_name='domains' AND column_name='version'
            """)) == "NO"
        command.downgrade(config, "20260809_0008")
        with engine.connect() as connection:
            assert connection.scalar(text("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_name='domains' AND column_name='version'
            """)) == 0
        command.upgrade(config, "20260812_0009")
    finally:
        engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set; PostgreSQL Alembic integration test skipped")
def test_alembic_upgrade_downgrade_upgrade_cycle_on_postgresql(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    if "test" not in (make_url(os.environ["TEST_DATABASE_URL"]).database or "").lower():
        pytest.fail("Refusing migration test outside a test database", pytrace=False)
    command = pytest.importorskip("alembic.command", reason="Alembic package is not installed", exc_type=ImportError)
    config_module = pytest.importorskip("alembic.config", reason="Alembic package is not installed", exc_type=ImportError)
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    config = config_module.Config("alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.downgrade(config, "base")


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_0006_preserves_dataset_reference_and_downgrades_multiple_domains(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = os.environ["TEST_DATABASE_URL"]
    if "test" not in (make_url(url).database or "").lower():
        pytest.fail("Refusing migration test outside a test database", pytrace=False)
    from alembic import command
    from alembic.config import Config
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "20260804_0005")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            mine = connection.scalar(text("INSERT INTO mines (name) VALUES ('migration') RETURNING id"))
            site = connection.scalar(text("INSERT INTO sites (mine_id, name) VALUES (:m, 'site') RETURNING id"), {"m": mine})
            workspace = connection.scalar(text("INSERT INTO assessment_workspaces (site_id) VALUES (:s) RETURNING id"), {"s": site})
            dataset_id = connection.scalar(text("""INSERT INTO project_lines_datasets
                (workspace_id, domain_id, name, imported_at, source_file_name, is_active, lines_json)
                VALUES (:w, 'D-X', 'X', now(), 'x.csv', true, '[]'::jsonb) RETURNING id"""), {"w": workspace})
            area = connection.scalar(text("""INSERT INTO assessment_areas
                (workspace_id, domain_id, name, assessment_date, is_archived)
                VALUES (:w, 'A-X', 'A', CURRENT_DATE, false) RETURNING id"""), {"w": workspace})
            revision = connection.scalar(text("""INSERT INTO assessment_area_geometry_revisions
                (assessment_area_id, domain_id, revision_number, created_at, source_dataset_id,
                 selection_polygon_json, final_geometry_json, lower_elevation_m, upper_elevation_m,
                 horizon_slices_json, change_reason, is_active)
                VALUES (:a, 'R-X', 1, now(), :d,
                 '{"type":"Polygon","coordinates":[]}'::jsonb,
                 '{"type":"Polygon","coordinates":[]}'::jsonb,
                 1, 2, '[]'::jsonb, NULL, true) RETURNING id"""), {"a": area, "d": dataset_id})
        command.upgrade(config, "20260807_0006")
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT id FROM project_lines_datasets WHERE domain_id='D-X'")) == dataset_id
            assert connection.scalar(text("SELECT source_dataset_id FROM assessment_area_geometry_revisions WHERE id=:r"), {"r": revision}) == dataset_id
            compatibility = connection.scalar(text("SELECT id FROM domains WHERE site_id=:s"), {"s": site})
            connection.execute(text("INSERT INTO domains (site_id, name) VALUES (:s, 'South')"), {"s": site})
            south = connection.scalar(text("SELECT id FROM domains WHERE site_id=:s AND name='South'"), {"s": site})
            connection.execute(text("INSERT INTO assessment_workspaces (domain_id) VALUES (:d)"), {"d": south})
            assert compatibility is not None
            no_workspace_site = connection.scalar(text(
                "INSERT INTO sites (mine_id, name) VALUES (:m, 'lines only') RETURNING id"), {"m": mine})
            no_workspace_domain = connection.scalar(text(
                "INSERT INTO domains (site_id, name) VALUES (:s, 'North') RETURNING id"),
                {"s": no_workspace_site})
            lines_only_dataset = connection.scalar(text("""INSERT INTO project_lines_datasets
                (site_id, domain_id, name, imported_at, source_file_name, is_active,
                 is_archived, lines_json)
                VALUES (:s, 'D-ONLY', 'Only', now(), 'only.csv', true, false, '[]'::jsonb)
                RETURNING id"""), {"s": no_workspace_site})
            assert no_workspace_domain is not None
        command.downgrade(config, "20260804_0005")
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT count(*) FROM assessment_workspaces WHERE site_id=:s"), {"s": site}) == 1
            assert connection.scalar(text("SELECT workspace_id FROM project_lines_datasets WHERE id=:d"), {"d": dataset_id}) is not None
            workspace_id = connection.scalar(text(
                "SELECT workspace_id FROM project_lines_datasets WHERE id=:d"),
                {"d": lines_only_dataset})
            assert workspace_id is not None
            assert connection.scalar(text(
                "SELECT site_id FROM assessment_workspaces WHERE id=:w"),
                {"w": workspace_id}) == no_workspace_site
    finally:
        engine.dispose()
        command.downgrade(config, "base")
