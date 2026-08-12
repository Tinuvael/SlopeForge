"""Concrete regression tests for the focused BlastBlock archive adapter."""
from __future__ import annotations

from datetime import date, timezone
from decimal import Decimal
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

URL = os.environ.get("SLOPEFORGE_TEST_DATABASE_URL")
if not URL:
    pytest.skip(
        "SLOPEFORGE_TEST_DATABASE_URL is not set; Block archive DB tests skipped",
        allow_module_level=True,
    )
if "test" not in (make_url(URL).database or "").lower():
    pytest.fail("Refusing destructive tests: PostgreSQL database name must contain 'test'", pytrace=False)

from database.assessment_models import BlastEvent
from database.models import AuditLogEntry, BlastBlock, Domain, Mine, Site
from infrastructure.db.blast_block_archive import SqlAlchemyBlastBlockArchivePersistence


@pytest.fixture(scope="module")
def session_factory(tmp_path_factory):
    old_database = os.environ.get("DATABASE_URL")
    old_storage = os.environ.get("STORAGE_ROOT")
    os.environ["DATABASE_URL"] = URL
    os.environ["STORAGE_ROOT"] = str(tmp_path_factory.mktemp("block-archive-storage"))
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
def linked_block(session_factory):
    suffix = uuid4().hex
    with session_factory.begin() as session:
        mine = Mine(name=f"Block archive mine {suffix}")
        session.add(mine); session.flush()
        site = Site(mine_id=mine.id, name=f"Block archive site {suffix}")
        session.add(site); session.flush()
        domain = Domain(site_id=site.id, name=f"Domain {suffix}")
        session.add(domain); session.flush()
        block = BlastBlock(
            domain_id=domain.id, block_number=f"B-{suffix[:8]}", horizon_m=Decimal("100"),
            planned_blast_date=date(2026, 8, 10), status="blasted", comment="unchanged",
            is_archived=False,
        )
        session.add(block); session.flush()
        blast_event = BlastEvent(
            domain_id=domain.id, logical_id="BE-P", name="Production",
            event_type="production", event_date=date(2026, 8, 10),
            elevation_m=Decimal("100"), blast_block_id=block.id, is_archived=False,
        )
        session.add(blast_event); session.flush()
        ids = mine.id, site.id, domain.id, block.id, blast_event.id
    yield ids
    mine_id, site_id, domain_id, block_id, _ = ids
    with session_factory.begin() as session:
        session.query(BlastBlock).filter_by(id=block_id).delete()
        session.query(Domain).filter_by(id=domain_id).delete()
        session.query(Site).filter_by(id=site_id).delete()
        session.query(Mine).filter_by(id=mine_id).delete()


def test_concrete_archive_restore_changes_only_block_archive_fields(session_factory, linked_block):
    *_, block_id, event_id = linked_block
    adapter = SqlAlchemyBlastBlockArchivePersistence(session_factory)
    with session_factory() as session:
        audit_before = session.scalar(select(func.count()).select_from(AuditLogEntry).where(
            AuditLogEntry.blast_block_id == block_id))

    adapter.set_archived(block_id, True, actor_id=123)
    with session_factory() as session:
        block = session.get(BlastBlock, block_id)
        production = session.get(BlastEvent, event_id)
        assert block.is_archived is True
        assert block.archived_at is not None and block.archived_at.tzinfo is not None
        assert block.archived_at.utcoffset() == timezone.utc.utcoffset(block.archived_at)
        assert block.status == "blasted" and block.comment == "unchanged"
        assert production.is_archived is False and production.archived_at is None
        assert session.scalar(select(func.count()).select_from(AuditLogEntry).where(
            AuditLogEntry.blast_block_id == block_id)) == audit_before

    adapter.set_archived(block_id, False, actor_id=123)
    with session_factory() as session:
        block = session.get(BlastBlock, block_id)
        production = session.get(BlastEvent, event_id)
        assert block.is_archived is False and block.archived_at is None
        assert block.status == "blasted"
        assert production.is_archived is False


def test_concrete_adapter_missing_block_and_commit_failure_roll_back(session_factory, linked_block):
    *_, block_id, _ = linked_block
    adapter = SqlAlchemyBlastBlockArchivePersistence(session_factory)
    with pytest.raises(ValueError, match="Blast block not found"):
        adapter.set_archived(2_000_000_000, True, actor_id=123)

    def fail_commit(_session):
        raise RuntimeError("injected commit failure")

    event.listen(session_factory.class_, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="injected commit failure"):
            adapter.set_archived(block_id, True, actor_id=123)
    finally:
        event.remove(session_factory.class_, "before_commit", fail_commit)
    with session_factory() as session:
        block = session.get(BlastBlock, block_id)
        assert block.is_archived is False and block.archived_at is None
