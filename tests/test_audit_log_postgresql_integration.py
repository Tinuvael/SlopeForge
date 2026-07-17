from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from database.app_context import CurrentUser
from database.models import AuditLogEntry, BlastBlock, Mine, Site, User
from repositories.audit_log_repository import AuditLogRepository
from repositories.blast_block_repository import BlastBlockRepository
from repositories.site_repository import SiteRepository
from services.blast_block_service import BlastBlockInput, BlastBlockService, PermissionDenied


class FailingAuditLogRepository(AuditLogRepository):
    def add_entry(self, *args, **kwargs):
        raise RuntimeError("audit failed")


@pytest.fixture()
def pg_session_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL is not set; PostgreSQL audit integration tests skipped")
    command = pytest.importorskip("alembic.command", reason="Alembic package is not installed", exc_type=ImportError)
    config_module = pytest.importorskip("alembic.config", reason="Alembic package is not installed", exc_type=ImportError)
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    config = config_module.Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield Session
    command.downgrade(config, "base")


@pytest.fixture()
def seeded_block(pg_session_factory):
    with pg_session_factory.begin() as session:
        user = User(username="admin", password_hash="hash", full_name="Admin User", role="admin", is_active=True)
        mine = Mine(name="Mine", description=None)
        session.add_all([user, mine]); session.flush()
        site = Site(mine_id=mine.id, name="Site A", description=None)
        site_b = Site(mine_id=mine.id, name="Site B", description=None)
        session.add_all([site, site_b]); session.flush()
        block = BlastBlock(site_id=site.id, block_number="B-001", horizon_m=None, planned_blast_date=None, status="planned", comment=None, created_by_user_id=user.id)
        session.add(block); session.flush()
        return {"user_id": user.id, "mine_id": mine.id, "site_id": site.id, "site_b_id": site_b.id, "block_id": block.id}


def service_for(Session, audit_repo=None):
    block_repo = BlastBlockRepository(Session)
    site_repo = SiteRepository(Session)
    return BlastBlockService(block_repo, site_repo, audit_repo)


def test_create_audit_entry_and_sorting(pg_session_factory):
    with pg_session_factory.begin() as session:
        user = User(username="admin", password_hash="hash", full_name="Admin User", role="admin", is_active=True)
        mine = Mine(name="Mine", description=None)
        session.add_all([user, mine]); session.flush()
        site = Site(mine_id=mine.id, name="Site A", description=None)
        session.add(site); session.flush()
        ids = {"user_id": user.id, "mine_id": mine.id, "site_id": site.id}
    service = service_for(pg_session_factory)
    block_id = service.create_block(BlastBlockInput("B-002", ids["mine_id"], ids["site_id"], "", None, "planned", ""), CurrentUser(ids["user_id"], "admin", "Admin User", "admin"))
    rows = AuditLogRepository(pg_session_factory).list_for_block(block_id)
    assert rows[0].action == "create"
    assert rows[0].description == "Создан взрывной блок"
    assert rows == sorted(rows, key=lambda row: (row.created_at, row.id), reverse=True)


def test_update_audit_only_changed_fields_and_noop_has_no_entries(pg_session_factory, seeded_block):
    service = service_for(pg_session_factory)
    user = CurrentUser(seeded_block["user_id"], "admin", "Admin User", "admin")
    service.update_block(seeded_block["block_id"], BlastBlockInput("B-001", seeded_block["mine_id"], seeded_block["site_b_id"], "760.500", date(2026, 7, 15), "blasted", "Updated"), user)
    rows = AuditLogRepository(pg_session_factory).list_for_block(seeded_block["block_id"])
    fields = [row.field_name for row in rows]
    assert set(fields) == {"site_id", "horizon_m", "planned_blast_date", "status", "comment"}
    assert any(row.old_value == "Site A" and row.new_value == "Site B" for row in rows)
    assert any(row.old_value == "Запланирован" and row.new_value == "Взорван" for row in rows)
    count = len(rows)
    service.update_block(seeded_block["block_id"], BlastBlockInput("B-001", seeded_block["mine_id"], seeded_block["site_b_id"], "760.5", date(2026, 7, 15), "blasted", "Updated"), user)
    assert len(AuditLogRepository(pg_session_factory).list_for_block(seeded_block["block_id"])) == count


def test_audit_failure_rolls_back_block_create(pg_session_factory, seeded_block):
    service = service_for(pg_session_factory, FailingAuditLogRepository(pg_session_factory))
    user = CurrentUser(seeded_block["user_id"], "admin", "Admin User", "admin")
    with pytest.raises(RuntimeError):
        service.create_block(BlastBlockInput("ROLLBACK", seeded_block["mine_id"], seeded_block["site_id"], "", None, "planned", ""), user)
    with pg_session_factory() as session:
        assert session.scalar(select(BlastBlock).where(BlastBlock.block_number == "ROLLBACK")) is None


def test_viewer_can_read_history_but_cannot_edit(pg_session_factory, seeded_block):
    repo = AuditLogRepository(pg_session_factory)
    assert repo.list_for_block(seeded_block["block_id"]) == []
    service = service_for(pg_session_factory)
    with pytest.raises(PermissionDenied):
        service.update_block(seeded_block["block_id"], BlastBlockInput("X", seeded_block["mine_id"], seeded_block["site_id"], "", None, "planned", ""), CurrentUser(999, "viewer", None, "viewer"))
