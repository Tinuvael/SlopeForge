from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url

from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision
from domain.assessment.geometry import (
    AssessmentBoundary, ProjectLineAnchor, ProjectLineSpan, SpatialPoint,
    StraightConnector, derive_elevation_summary, derive_plan_polygon,
)
from domain.geometry.types import DatamineLine, DataminePoint
from domain.project.project_lines import ProjectLinesDataset


def _build_mvp_assessment_fixture() -> tuple[ProjectLinesDataset, AssessmentArea]:
    """Build the real post-#89 domain fixture independently of PostgreSQL."""
    source_line = DatamineLine(
        source_id="crest-1",
        points=[
            DataminePoint(
                x=0.0, y=0.0, z=101.12349, source_row_number=1,
            ),
            DataminePoint(
                x=10.0, y=0.0, z=109.98751, source_row_number=2,
            ),
        ],
        import_order=0,
    )
    dataset = ProjectLinesDataset(
        id="LINES-1",
        name="Survey",
        imported_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
        source_file_name="survey.csv",
        is_active=True,
        lines=[source_line],
    )
    start_point = SpatialPoint(x=0.0, y=0.0, z=101.12349)
    end_point = SpatialPoint(x=10.0, y=0.0, z=109.98751)
    start_anchor = ProjectLineAnchor(
        source_dataset_id="LINES-1", source_line_id="crest-1",
        source_segment_index=0, interpolation_fraction=0.0,
        frozen_point_xyz=start_point,
    )
    end_anchor = ProjectLineAnchor(
        source_dataset_id="LINES-1", source_line_id="crest-1",
        source_segment_index=0, interpolation_fraction=1.0,
        frozen_point_xyz=end_point,
    )
    corner = SpatialPoint(x=4.0, y=8.0, z=None)
    boundary = AssessmentBoundary(segments=(
        ProjectLineSpan(
            start_anchor=start_anchor, end_anchor=end_anchor,
            frozen_trace_xyz=(start_point, end_point),
        ),
        StraightConnector(
            start_point=end_point, end_point=corner, start_anchor=end_anchor,
        ),
        StraightConnector(
            start_point=corner, end_point=start_point, end_anchor=start_anchor,
        ),
    ))
    minimum, maximum = derive_elevation_summary(boundary)
    area = AssessmentArea(
        id="AREA-1",
        name="North wall",
        assessment_date=date(2026, 8, 13),
        geometry_revisions=[AssessmentAreaGeometryRevision(
            id="GEOM-1",
            assessment_area_id="AREA-1",
            revision_number=1,
            created_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
            boundary=boundary,
            final_geometry_frozen=derive_plan_polygon(boundary),
            min_elevation=minimum,
            max_elevation=maximum,
            change_reason="Initial traced boundary",
        )],
        active_geometry_revision_id="GEOM-1",
    )
    return dataset, area


def test_mvp_assessment_fixture_uses_canonical_domain_serialization() -> None:
    dataset, area = _build_mvp_assessment_fixture()
    source_line = dataset.lines[0]
    assert source_line.source_id == "crest-1"
    assert source_line.import_order == 0
    assert [(point.x, point.y, point.z, point.source_row_number)
            for point in source_line.points] == [
        (0.0, 0.0, 101.12349, 1),
        (10.0, 0.0, 109.98751, 2),
    ]
    revision = area.active_geometry_revision()
    assert derive_plan_polygon(revision.boundary) == revision.final_geometry_frozen
    assert derive_elevation_summary(revision.boundary) == (101.12349, 109.98751)
    assert (revision.min_elevation, revision.max_elevation) == (101.12349, 109.98751)
    assert ProjectLinesDataset.from_dict(dataset.to_dict()).to_dict() == dataset.to_dict()
    restored = AssessmentArea.from_dict(area.to_dict())
    assert restored.to_dict() == area.to_dict()
    assert restored.active_geometry_revision().boundary == revision.boundary


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


def test_phase_75a_migration_is_the_only_alembic_head() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["0002_derive_blast_workflow_status"]
    assert [revision.revision for revision in script.walk_revisions()] == [
        "0002_derive_blast_workflow_status",
        "0001_mvp_baseline"
    ]


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_mvp_baseline_upgrade_application_smoke_and_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exercise the real post-#89 model against a DB created only from 0001."""
    from alembic import command
    from database import assessment_models as orm
    from database.models import BlastBlock, Domain, Mine, Site
    from infrastructure.db.assessment_writes import SqlAlchemyAssessmentWrites
    from repositories.assessment_state_repository import AssessmentStateRepository
    from repositories.project_lines_repository import ProjectLinesRepository

    url = os.environ["TEST_DATABASE_URL"]
    config = _alembic_config(monkeypatch, tmp_path, url)
    engine = create_engine(url)
    sessions = sessionmaker(engine, expire_on_commit=False)

    def create_core_graph() -> tuple[int, int]:
        with sessions.begin() as session:
            mine = Mine(name="MVP baseline")
            session.add(mine); session.flush()
            site = Site(mine_id=mine.id, name="Project")
            session.add(site); session.flush()
            domain = Domain(site_id=site.id, name="North")
            session.add(domain); session.flush()
            block = BlastBlock(
                domain_id=domain.id, block_number="B-1",
                is_archived=False,
            )
            session.add(block); session.flush()
            session.add_all([
                orm.BlastEvent(
                    domain_id=domain.id, logical_id="PROD-1", name="Production",
                    event_type="production", elevation_m=Decimal("100.000"),
                    blast_block_id=block.id, is_archived=False,
                ),
                orm.BlastEvent(
                    domain_id=domain.id, logical_id="CONT-1", name="Contour",
                    event_type="contour", elevation_m=Decimal("105.000"),
                    is_archived=False,
                ),
            ])
            return site.id, domain.id

    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        site_id, domain_id = create_core_graph()

        # Reuse the domain fixture covered by a normal, non-DB regression test.
        dataset, area = _build_mvp_assessment_fixture()
        ProjectLinesRepository(sessions).import_dataset(
            site_id, dataset, make_active=True
        )
        boundary = area.active_geometry_revision().boundary
        minimum, maximum = derive_elevation_summary(boundary)
        result = SqlAlchemyAssessmentWrites(sessions).persist_assessment_area_geometry(
            domain_id, 0, area
        )
        loaded = AssessmentStateRepository(sessions).load_for_domain(domain_id)
        loaded_area = loaded.state.assessment_areas[0]
        loaded_revision = loaded_area.active_geometry_revision()
        assert loaded.expected_version == result.new_version == 1
        assert loaded_area.id == "AREA-1"
        assert loaded_revision.boundary == boundary
        assert loaded_revision.final_geometry_frozen == derive_plan_polygon(boundary)
        assert (loaded_revision.min_elevation, loaded_revision.max_elevation) == (minimum, maximum)
        assert [type(segment).__name__ for segment in loaded_revision.boundary.segments] == [
            "ProjectLineSpan", "StraightConnector", "StraightConnector"
        ]
        assert {event.id for event in loaded.state.blast_events} == {"PROD-1", "CONT-1"}
        assert loaded.state.active_dataset().id == "LINES-1"
        with sessions() as session:
            stored = session.scalar(select(orm.AssessmentAreaGeometryRevision))
            assert stored.min_elevation_m == Decimal("101.123")
            assert stored.max_elevation_m == Decimal("109.988")

        command.downgrade(config, "base")
        assert "users" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        _, rebuilt_domain_id = create_core_graph()
        rebuilt = AssessmentStateRepository(sessions).load_for_domain(rebuilt_domain_id)
        assert {event.id for event in rebuilt.state.blast_events} == {"PROD-1", "CONT-1"}
        assert rebuilt.state.assessment_areas == []
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
            assert set(actual_columns) == set(model_table.columns.keys()), name
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
