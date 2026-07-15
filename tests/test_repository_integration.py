from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Mine, Site
from repositories.mine_repository import MineRepository
from repositories.site_repository import SiteRepository


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set; PostgreSQL integration tests skipped")
def test_create_mine_and_site_in_postgresql() -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    mine_repo = MineRepository(Session)
    site_repo = SiteRepository(Session)
    mine = mine_repo.create_mine("Test mine", "description")
    site = site_repo.create_site(mine.id, "Test site", None)
    assert site.mine_id == mine.id
