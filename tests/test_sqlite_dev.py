from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.app_context import CurrentUser
from database.models import User
from database.settings import Settings
from repositories.blast_block_repository import BlastBlockRepository
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository
from services.blast_block_service import BlastBlockInput, BlastBlockService


@pytest.mark.usefixtures("monkeypatch")
def test_sqlite_dev_settings_require_explicit_mode_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_MODE", "sqlite-dev")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///slopeforge_dev.db")
    monkeypatch.setenv("STORAGE_ROOT", "./storage")
    settings = Settings.from_env()
    assert settings.is_sqlite_dev


def test_sqlite_dev_smoke_create_schema_and_block(tmp_path: Path) -> None:
    pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.users import create_first_admin_with_lock

    db_path = tmp_path / "slopeforge_dev.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with Session.begin() as session:
        admin_user = create_first_admin_with_lock(session, "admin", "password", "Admin")
        admin_id = admin_user.id

    mine_repo = MineRepository(Session)
    site_repo = SiteRepository(Session)
    block_repo = BlastBlockRepository(Session)
    service = BlastBlockService(block_repo, site_repo)

    mine = mine_repo.create_mine("Dev mine", None)
    site = site_repo.create_site(mine.id, "Dev site", None)
    block_id = service.create_block(
        BlastBlockInput(
            block_number="DEV-001",
            mine_id=mine.id,
            site_id=site.id,
            horizon_text="10.5",
            planned_blast_date=None,
            status="planned",
            comment="sqlite dev smoke",
        ),
        CurrentUser(id=admin_id, username="admin", full_name="Admin", role="admin"),
    )
    rows = service.list_blocks(number_query="DEV", site_id=site.id, status="planned")
    assert [row.id for row in rows] == [block_id]
