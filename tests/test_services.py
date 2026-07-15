from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from database.app_context import CurrentUser
from services.auth_service import AuthError, AuthService
from services.blast_block_service import BlastBlockInput, BlastBlockService, PermissionDenied, ValidationError


admin = CurrentUser(id=1, username="admin", full_name="Admin", role="admin")
editor = CurrentUser(id=2, username="editor", full_name=None, role="editor")
viewer = CurrentUser(id=3, username="viewer", full_name=None, role="viewer")


@dataclass
class FakeSite:
    id: int
    mine_id: int
    name: str = "site"


class FakeSiteRepo:
    def __init__(self):
        self.sites = [FakeSite(id=10, mine_id=20)]
    def list_sites(self, mine_id=None):
        return [s for s in self.sites if mine_id is None or s.mine_id == mine_id]


class FakeBlockRepo:
    def __init__(self):
        self.created = []
        self.updated = []
        self.rows = [
            type("Row", (), {"id": 1, "block_number": "24-001", "site_id": 10, "status": "planned"})(),
            type("Row", (), {"id": 2, "block_number": "25-002", "site_id": 11, "status": "blasted"})(),
        ]
    def create_block(self, **kwargs):
        self.created.append(kwargs)
        return type("Block", (), {"id": 100})()
    def update_block(self, **kwargs):
        self.updated.append(kwargs)
        return type("Block", (), {"id": kwargs["block_id"]})()
    def list_blocks(self, number_query=None, mine_id=None, site_id=None, status=None):
        rows = self.rows
        if number_query:
            rows = [r for r in rows if number_query in r.block_number]
        if site_id is not None:
            rows = [r for r in rows if r.site_id == site_id]
        if status:
            rows = [r for r in rows if r.status == status]
        return rows
    def get_block(self, block_id):
        return next((r for r in self.rows if r.id == block_id), None)


def valid_input(**overrides):
    data = {
        "block_number": "24-017",
        "mine_id": 20,
        "site_id": 10,
        "horizon_text": "135.5",
        "planned_blast_date": None,
        "status": "planned",
        "comment": "",
    }
    data.update(overrides)
    return BlastBlockInput(**data)


def test_roles_can_edit() -> None:
    assert admin.can_edit
    assert editor.can_edit
    assert not viewer.can_edit


def test_create_block_success() -> None:
    repo = FakeBlockRepo(); service = BlastBlockService(repo, FakeSiteRepo())
    block_id = service.create_block(valid_input(), admin)
    assert block_id == 100
    assert repo.created[0]["horizon_m"] == Decimal("135.5")


def test_update_existing_block_success() -> None:
    repo = FakeBlockRepo(); service = BlastBlockService(repo, FakeSiteRepo())
    block_id = service.update_block(5, valid_input(block_number="24-018"), editor)
    assert block_id == 5
    assert repo.updated[0]["block_number"] == "24-018"


def test_filter_blocks_by_number_site_and_status() -> None:
    service = BlastBlockService(FakeBlockRepo(), FakeSiteRepo())
    assert [r.id for r in service.list_blocks(number_query="24", site_id=10, status="planned")] == [1]


def test_viewer_cannot_edit() -> None:
    service = BlastBlockService(FakeBlockRepo(), FakeSiteRepo())
    with pytest.raises(PermissionDenied):
        service.create_block(valid_input(), viewer)


def test_block_validation_rejects_bad_site_and_status() -> None:
    service = BlastBlockService(FakeBlockRepo(), FakeSiteRepo())
    with pytest.raises(ValidationError):
        service.create_block(valid_input(site_id=99), admin)
    with pytest.raises(ValidationError):
        service.create_block(valid_input(status="bad"), admin)


def test_auth_success_and_failure_with_fake_session() -> None:
    pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.models import User
    from database.security import hash_password

    class FakeScalarResult:
        def __init__(self, user): self.user = user
    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def scalar(self, statement): return self.user
    user = User(id=1, username="admin", password_hash=hash_password("secret"), full_name="Admin", role="admin", is_active=True)
    fake_session = FakeSession(); fake_session.user = user
    auth = AuthService(lambda: fake_session)
    assert auth.authenticate("admin", "secret").role == "admin"
    with pytest.raises(AuthError):
        auth.authenticate("admin", "wrong")


def test_repository_rolls_back_when_save_fails() -> None:
    from repositories.mine_repository import MineRepository

    class FailingSession:
        def __init__(self): self.rolled_back = False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def add(self, item): raise RuntimeError("database failure")
        def commit(self): pass
        def rollback(self): self.rolled_back = True

    session = FailingSession()
    repo = MineRepository(lambda: session)
    with pytest.raises(RuntimeError):
        repo.create_mine("Mine", None)
    assert session.rolled_back
