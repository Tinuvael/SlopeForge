from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repositories.site_repository import SiteRepository


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set; PostgreSQL integration tests skipped")
def test_create_project_site_directly_in_postgresql() -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    repo = SiteRepository(Session)
    site = repo.create_site("Test project", "description")
    assert site.id is not None
    assert site.name == "Test project"
    assert not hasattr(site, "mine_id")
