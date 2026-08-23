from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os

import pytest

pytestmark = pytest.mark.postgres
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from tests.postgres_test_database import is_disposable_test_database

URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    pytest.skip(
        "TEST_DATABASE_URL is not set; drillhole PostgreSQL tests skipped",
        allow_module_level=True,
    )
if not is_disposable_test_database(URL):
    pytest.fail(
        "Refusing destructive drillhole tests outside a test database",
        pytrace=False,
    )

from database.assessment_models import BlastEvent
from database.drillhole_models import BlastEventDrillholeDataset
from database.models import Domain, Site
from repositories.drillhole_dataset_repository import (
    BlastEventDrillholeDatasetRepository,
    DrillholeDatasetConflictError,
)


@pytest.fixture(scope="module")
def factory():
    old_database = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = URL
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if old_database is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_database
    engine = create_engine(URL)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def _source_file(name: str) -> dict[str, object]:
    return {
        "original_filename": name,
        "stored_filename": name,
        "relative_path": f"files/blast_events/test/{name}",
        "file_size_bytes": 123,
        "sha256": "a" * 64,
    }


def _hole(hole_id: str, *, group_id: str | None = None) -> dict[str, object]:
    return {
        "hole_id": hole_id,
        "points": [
            {"x": 0.0, "y": 0.0, "z": 630.0},
            {"x": 0.0, "y": 0.0, "z": 620.0},
        ],
        "engineering_group_id": group_id,
        "source_attributes": {"stable_hole_id": True},
    }


def _add(
    repository,
    domain_id: int,
    event_id: str,
    logical_id: str,
    kind: str,
    *,
    matched_design_dataset_id: int | None = None,
    holes=None,
):
    hole_values = list(holes or [_hole("H-1")])
    return repository.add_dataset(
        domain_id,
        event_id,
        logical_id=logical_id,
        dataset_kind=kind,
        matched_design_dataset_id=matched_design_dataset_id,
        imported_at=datetime.now(timezone.utc),
        imported_by_user_id=None,
        source_format="datamine",
        source_files=[_source_file(f"{logical_id}.dmx")],
        holes=hole_values,
        summary={"hole_count": len(hole_values), "total_drilling_length_m": 10.0},
        matches=[],
        hole_count=len(hole_values),
        total_drilling_length_m=10.0 * len(hole_values),
    )


@pytest.fixture
def event_graph(factory):
    with factory.begin() as session:
        site = Site(name=f"Drillhole repo {datetime.now(timezone.utc).timestamp()}")
        session.add(site)
        session.flush()
        domain = Domain(site_id=site.id, name="North")
        session.add(domain)
        session.flush()
        first = BlastEvent(
            domain_id=domain.id,
            logical_id="BE-DRILL-1",
            name="Block 1",
            event_type="production",
            elevation_m=Decimal("630.000"),
            is_archived=False,
        )
        second = BlastEvent(
            domain_id=domain.id,
            logical_id="BE-DRILL-2",
            name="Block 2",
            event_type="production",
            elevation_m=Decimal("630.000"),
            is_archived=False,
        )
        session.add_all([first, second])
        session.flush()
        ids = (site.id, domain.id, first.id, second.id)
    yield ids
    site_id, domain_id, first_id, second_id = ids
    with factory.begin() as session:
        session.execute(
            delete(BlastEventDrillholeDataset).where(
                BlastEventDrillholeDataset.blast_event_id.in_([first_id, second_id])
            )
        )
        session.execute(delete(BlastEvent).where(BlastEvent.id.in_([first_id, second_id])))
        session.execute(delete(Domain).where(Domain.id == domain_id))
        session.execute(delete(Site).where(Site.id == site_id))


def test_latest_revision_is_current_per_event_and_kind(factory, event_graph) -> None:
    _site_id, domain_id, _first_pk, _second_pk = event_graph
    repository = BlastEventDrillholeDatasetRepository(factory)

    design_1 = _add(repository, domain_id, "BE-DRILL-1", "DH-D-1", "design")
    design_2 = _add(repository, domain_id, "BE-DRILL-1", "DH-D-2", "design")
    actual_1 = _add(
        repository,
        domain_id,
        "BE-DRILL-1",
        "DH-A-1",
        "actual",
        matched_design_dataset_id=design_2.id,
    )

    assert (design_1.revision_number, design_2.revision_number) == (1, 2)
    assert actual_1.revision_number == 1
    assert repository.get_current(domain_id, "BE-DRILL-1", "design").id == design_2.id
    assert repository.get_current(domain_id, "BE-DRILL-1", "actual").id == actual_1.id
    assert [
        row.revision_number
        for row in repository.list_for_event(
            domain_id, "BE-DRILL-1", dataset_kind="design"
        )
    ] == [2, 1]


def test_actual_cannot_reference_design_from_another_blast_event(factory, event_graph) -> None:
    _site_id, domain_id, _first_pk, _second_pk = event_graph
    repository = BlastEventDrillholeDatasetRepository(factory)
    foreign_design = _add(
        repository, domain_id, "BE-DRILL-2", "DH-FOREIGN", "design"
    )

    with pytest.raises(ValueError, match="different Blast Event"):
        _add(
            repository,
            domain_id,
            "BE-DRILL-1",
            "DH-ACTUAL-BAD",
            "actual",
            matched_design_dataset_id=foreign_design.id,
        )


def test_group_assignment_updates_only_current_design_revision(factory, event_graph) -> None:
    _site_id, domain_id, _first_pk, _second_pk = event_graph
    repository = BlastEventDrillholeDatasetRepository(factory)
    first = _add(repository, domain_id, "BE-DRILL-1", "DH-CURRENT-1", "design")

    updated = repository.update_holes(first.id, [_hole("H-1", group_id="MAIN")])
    assert updated.holes_json[0]["engineering_group_id"] == "MAIN"

    _add(repository, domain_id, "BE-DRILL-1", "DH-CURRENT-2", "design")
    with pytest.raises(DrillholeDatasetConflictError, match="changed while group assignments"):
        repository.update_holes(first.id, [_hole("H-1", group_id="BUFFER")])

    historical = repository.get_by_logical_id(
        domain_id, "BE-DRILL-1", "DH-CURRENT-1"
    )
    assert historical.holes_json[0]["engineering_group_id"] == "MAIN"
