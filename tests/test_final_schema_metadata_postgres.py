from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")
def test_fresh_head_matches_application_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fresh PostgreSQL at Alembic head must match the final ORM schema."""
    from alembic import command
    from alembic.config import Config
    from database.base import Base
    import database.assessment_models  # noqa: F401
    import database.models  # noqa: F401

    url = os.environ["TEST_DATABASE_URL"]
    if "test" not in (make_url(url).database or "").lower():
        pytest.fail("Refusing migration test outside a test database", pytrace=False)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    config = Config("alembic.ini")
    engine = create_engine(url)
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= set(Base.metadata.tables)
        assert "mines" not in inspector.get_table_names()
        assert "blast_blocks" not in inspector.get_table_names()
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
            expected_checks = {
                check.name for check in model_table.constraints
                if check.__class__.__name__ == "CheckConstraint"
            }
            assert expected_checks <= actual_checks
    finally:
        engine.dispose()
