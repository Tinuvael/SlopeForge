from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from database.base import Base
from database.models import User
from database import assessment_models  # noqa: F401  Register the complete ORM graph.
from database.settings import Settings
from database.storage import StoragePathError, copy_attachment, ensure_inside_storage


def test_password_hashing_and_verification() -> None:
    pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.security import hash_password, verify_password
    password_hash = hash_password("strong-password")
    assert password_hash.startswith("$argon2")
    assert verify_password("strong-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_first_user_admin_logic_with_mocked_session() -> None:
    pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.users import create_user
    class FakeSession:
        def __init__(self) -> None:
            self.users: list[User] = []
        def scalar(self, _statement): return len(self.users)
        def add(self, user: User) -> None: self.users.append(user)
        def flush(self) -> None: pass

    session = FakeSession()
    first = create_user(session, "admin", "password")
    second = create_user(session, "viewer", "password")
    assert first.role == "admin"
    assert second.role == "viewer"


def test_attachment_storage_uses_site_and_blast_event_identity(tmp_path: Path) -> None:
    settings = Settings(database_url="postgresql+psycopg://u:p@localhost:5432/db", storage_root=tmp_path / "storage")
    source = tmp_path / "source photo.jpg"; source.write_text("content")
    relative_path = copy_attachment(source, site_id=2, event_id="BE-PROD-3", settings=settings)
    assert not relative_path.is_absolute()
    assert "mine_" not in str(relative_path) and "block_" not in str(relative_path)
    assert "site_2" in str(relative_path) and "blast_event_BE-PROD-3" in str(relative_path)
    assert (settings.storage_root / relative_path).read_text() == "content"
    with pytest.raises(StoragePathError): ensure_inside_storage(tmp_path / "outside.txt", settings=settings)


def test_sqlalchemy_metadata_compiles_for_postgresql_and_has_no_legacy_tables() -> None:
    assert "users" in Base.metadata.tables
    assert "sites" in Base.metadata.tables and "blast_events" in Base.metadata.tables
    assert "mines" not in Base.metadata.tables
    assert "blast_blocks" not in Base.metadata.tables
    assert "mine_id" not in Base.metadata.tables["sites"].c
    assert "blast_block_id" not in Base.metadata.tables["blast_events"].c
    for table in Base.metadata.sorted_tables:
        str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_release_1_frozen_core_is_self_contained() -> None:
    migration = Path("alembic/schema_v1/core.py").read_text()
    assert "from database.base import Base" not in migration
    assert "from database import models" not in migration
    assert "create_all" not in migration
    assert "op.create_table" in migration
    assert "op.drop_table" in migration
    assert "user_role" in migration
    assert "blast_block_status" not in migration
    assert "mines" not in migration
    assert "blast_blocks" not in migration


def test_release_1_frozen_components_resolve_all_runtime_names(monkeypatch) -> None:
    """Calling frozen component functions catches undefined names hidden from compileall."""
    from importlib.util import module_from_spec, spec_from_file_location

    class NoOpOperations:
        def __getattr__(self, _name): return lambda *args, **kwargs: None

    for component in ("core", "project_surfaces", "drillhole_datasets"):
        path = Path(f"alembic/schema_v1/{component}.py")
        spec = spec_from_file_location(f"release_1_{component}_runtime_names", path)
        module = module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
        monkeypatch.setattr(module, "op", NoOpOperations())
        monkeypatch.setattr(module.sa.Enum, "drop", lambda *args, **kwargs: None)
        module.upgrade(); module.downgrade()


def test_first_admin_creation_uses_advisory_lock_and_rechecks_users() -> None:
    pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.users import FirstAdminAlreadyExistsError, create_first_admin_with_lock

    class FakeDialect: name = "postgresql"
    class FakeBind: dialect = FakeDialect()
    class FakeSession:
        def __init__(self, count: int): self.count = count; self.executed = []; self.added = []
        def get_bind(self): return FakeBind()
        def execute(self, statement, params=None): self.executed.append((str(statement), params))
        def scalar(self, statement): return self.count
        def add(self, user): self.added.append(user)
        def flush(self): pass

    empty_session = FakeSession(0)
    user = create_first_admin_with_lock(empty_session, "admin", "password")
    assert "pg_advisory_xact_lock" in empty_session.executed[0][0]
    assert user.role == "admin"

    existing_session = FakeSession(1)
    with pytest.raises(FirstAdminAlreadyExistsError): create_first_admin_with_lock(existing_session, "other", "password")
    assert "pg_advisory_xact_lock" in existing_session.executed[0][0]
    assert existing_session.added == []
