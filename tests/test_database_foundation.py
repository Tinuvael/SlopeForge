from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from database.base import Base
from database.models import ChargeSegment, RockMassProfile, RockStructure, User
from database.settings import Settings
from database.storage import StoragePathError, copy_attachment, ensure_inside_storage


def constraint_names(table_name: str, constraint_type: type) -> set[str]:
    return {c.name for c in Base.metadata.tables[table_name].constraints if isinstance(c, constraint_type)}


def test_password_hashing_and_verification() -> None:
    argon2 = pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.security import hash_password, verify_password
    password_hash = hash_password("strong-password")
    assert password_hash.startswith("$argon2")
    assert verify_password("strong-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_range_constraints_are_declared() -> None:
    rock_constraints = constraint_names(RockMassProfile.__tablename__, CheckConstraint)
    structure_constraints = constraint_names(RockStructure.__tablename__, CheckConstraint)
    assert "ck_rock_mass_profiles_rqd_percent_range" in rock_constraints
    assert "ck_rock_mass_profiles_rmr_range" in rock_constraints
    assert "ck_rock_mass_profiles_gsi_range" in rock_constraints
    assert "ck_rock_structures_dip_deg_range" in structure_constraints
    assert "ck_rock_structures_dip_direction_deg_range" in structure_constraints


def test_charge_segment_order_is_unique() -> None:
    constraints = constraint_names(ChargeSegment.__tablename__, UniqueConstraint)
    assert "uq_charge_segments_pattern_sequence" in constraints


def test_first_user_admin_logic_with_mocked_session() -> None:
    pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.users import create_user
    class FakeSession:
        def __init__(self) -> None:
            self.users: list[User] = []
        def scalar(self, _statement):
            return len(self.users)
        def add(self, user: User) -> None:
            self.users.append(user)
        def flush(self) -> None:
            pass

    session = FakeSession()
    first = create_user(session, "admin", "password")
    second = create_user(session, "viewer", "password")
    assert first.role == "admin"
    assert second.role == "viewer"


def test_attachment_storage_rejects_escape_and_copies_file(tmp_path: Path) -> None:
    settings = Settings(database_url="postgresql+psycopg://u:p@localhost:5432/db", storage_root=tmp_path / "storage")
    source = tmp_path / "source photo.jpg"
    source.write_text("content")
    relative_path = copy_attachment(source, mine_id=1, site_id=2, block_id=3, settings=settings)
    assert not relative_path.is_absolute()
    assert (settings.storage_root / relative_path).read_text() == "content"
    with pytest.raises(StoragePathError):
        ensure_inside_storage(tmp_path / "outside.txt", settings=settings)


def test_sqlalchemy_metadata_compiles_for_postgresql() -> None:
    assert "users" in Base.metadata.tables
    for table in Base.metadata.sorted_tables:
        str(CreateTable(table).compile(dialect=postgresql.dialect()))
