"""PostgreSQL Domain concurrency and rollback coverage."""
import os
from datetime import date

import pytest

pytestmark = pytest.mark.postgres
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from tests.postgres_test_database import is_disposable_test_database
from tests.geometry_test_files import write_production_dxf
from sqlalchemy.orm import sessionmaker

URL = os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)
if not is_disposable_test_database(URL):
    pytest.fail("Refusing destructive tests outside a database containing 'test'", pytrace=False)

from application.errors import DomainConcurrencyConflict
from application.use_cases.create_blast_event import CreateBlastEvent, CreateBlastEventCommand
from database import assessment_models as orm
from database.models import AuditLogEntry, Domain, Site
from domain.blasting.entities import BlastEvent
from infrastructure.db.assessment_writes import SqlAlchemyAssessmentWrites
from infrastructure.db.blast_event_creation import SqlAlchemyBlastEventCreationPersistence
from infrastructure.db.domain_version import guard_domain_versions


@pytest.fixture(scope="module")
def factory(tmp_path_factory):
    old_database = os.environ.get("DATABASE_URL")
    old_storage = os.environ.get("STORAGE_ROOT")
    os.environ["DATABASE_URL"] = URL
    os.environ["STORAGE_ROOT"] = str(tmp_path_factory.mktemp("domain-concurrency-storage"))
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if old_database is None: os.environ.pop("DATABASE_URL", None)
        else: os.environ["DATABASE_URL"] = old_database
        if old_storage is None: os.environ.pop("STORAGE_ROOT", None)
        else: os.environ["STORAGE_ROOT"] = old_storage
    engine = create_engine(URL)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def domains(factory):
    with factory.begin() as session:
        site = Site(name="domain concurrency site"); session.add(site); session.flush()
        first = Domain(site_id=site.id, name="A"); second = Domain(site_id=site.id, name="B")
        session.add_all((first, second)); session.flush()
        ids = first.id, second.id, site.id
    yield ids


def versions(factory, *ids):
    with factory() as session:
        return tuple(session.get(Domain, item).version for item in ids)


def test_single_and_multi_domain_cas_and_failure_rollback(factory, domains):
    a, b, *_ = domains
    with factory.begin() as session:
        assert guard_domain_versions(session, {a: 0}) == {a: 1}
    assert versions(factory, a, b) == (1, 0)
    with pytest.raises(RuntimeError):
        with factory.begin() as session:
            guard_domain_versions(session, {a: 1})
            session.add(orm.BlastEvent(
                domain_id=a, logical_id="ROLLBACK", name="Rollback production",
                event_type="production", event_date=date.today(), elevation_m=100,
            ))
            session.flush()
            raise RuntimeError("after guard")
    assert versions(factory, a, b) == (1, 0)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(orm.BlastEvent)) == 0
    with factory.begin() as session:
        assert guard_domain_versions(session, {b: 0, a: 1}) == {a: 2, b: 1}
    assert versions(factory, a, b) == (2, 1)
    for stale in ({a: 1, b: 1}, {a: 2, b: 0}):
        with pytest.raises(DomainConcurrencyConflict):
            with factory.begin() as session: guard_domain_versions(session, stale)
        assert versions(factory, a, b) == (2, 1)


def test_two_stale_focused_assessment_sessions(factory, domains):
    domain_id, *_ = domains
    with factory.begin() as session:
        row = orm.BlastEvent(domain_id=domain_id, logical_id="C-1", name="Contour",
                             event_type="contour", event_date=date.today(), elevation_m=100)
        session.add(row)
    event_a = BlastEvent("C-1", "Contour", "contour", date.today(), 100)
    event_b = BlastEvent("C-1", "Contour", "contour", date.today(), 100)
    event_a.archive(); event_b.archive()
    writes = SqlAlchemyAssessmentWrites(factory)
    result = writes.persist_contour_archive(domain_id, 0, event_a)
    assert result.new_version == 1
    with pytest.raises(DomainConcurrencyConflict):
        writes.persist_contour_archive(domain_id, 0, event_b)
    assert versions(factory, domain_id) == (1,)
    event_b.restore()
    assert writes.persist_contour_archive(domain_id, 1, event_b).new_version == 2
    assert versions(factory, domain_id) == (2,)


def test_production_event_version_and_children_commit_or_roll_back(factory, domains, tmp_path):
    domain_id, *_ = domains
    geometry = write_production_dxf(tmp_path / "blast.dxf", elevation=100,
                                    ring=((0,0),(10,0),(10,10),(0,10),(0,0)))
    use_case = CreateBlastEvent(SqlAlchemyBlastEventCreationPersistence(factory))
    result = use_case.execute(CreateBlastEventCommand(
        domain_id, "P-1", "production", date.today(), 100, str(geometry), None, True))
    assert result.event_type == "production" and versions(factory, domain_id) == (1,)
    with factory() as session:
        persisted = session.scalar(select(orm.BlastEvent).where(
            orm.BlastEvent.logical_id == result.event_id
        ))
        assert persisted is not None and persisted.event_type == "production"
        assert session.scalar(select(func.count()).select_from(orm.BlastEvent)) == 1
        audit_rows = list(session.scalars(select(AuditLogEntry).order_by(AuditLogEntry.id)))
        assert [(row.action, row.field_name, row.description) for row in audit_rows] == [
            ("create", None, "Block created"),
            ("update", "geometry_revision", "Geometry imported"),
        ]
    failing = CreateBlastEvent(SqlAlchemyBlastEventCreationPersistence(
        factory, failure_hook=lambda stage: (_ for _ in ()).throw(RuntimeError(stage))
        if stage == "after_event_flush" else None))
    with pytest.raises(RuntimeError):
        failing.execute(CreateBlastEventCommand(
            domain_id, "P-2", "production", date.today(), 100, str(geometry), None, True))
    assert versions(factory, domain_id) == (1,)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(orm.BlastEvent)) == 1
        assert session.scalar(select(func.count()).select_from(
            orm.BlastEventGeometryRevision
        )) == 1
        assert session.scalar(select(func.count()).select_from(AuditLogEntry)) == 2
