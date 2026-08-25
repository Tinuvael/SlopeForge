from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.postgres
@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_release_1_database_records_alembic_revision_one() -> None:
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "1"
    finally:
        engine.dispose()
