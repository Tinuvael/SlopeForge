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
class FakeDomain:
    id: int
    site_id: int = 10
    name: str = "North"

class FakeDomainRepo:
    def __init__(self): self.domains = [FakeDomain(7)]
    def get(self, domain_id): return next((x for x in self.domains if x.id == domain_id), None)

class FakeBlockRepo:
    session_factory = None
    def __init__(self): self.created=[]; self.updated=[]; self.rows=[]
    def create_block(self, **kwargs): self.created.append(kwargs); return type("Block",(),{"id":100})()
    def update_block(self, **kwargs): self.updated.append(kwargs); return type("Block",(),{"id":kwargs["block_id"]})()
    def list_blocks(self, **filters): return self.rows
    def get_block(self, block_id): return None

def valid_input(**overrides):
    data={"domain_id":7,"block_number":"24-017","horizon_text":"135.5","planned_blast_date":None,"status":"planned","comment":""}; data.update(overrides); return BlastBlockInput(**data)

def test_roles_can_edit(): assert admin.can_edit and editor.can_edit and not viewer.can_edit
def test_create_block_by_domain():
    repo=FakeBlockRepo(); service=BlastBlockService(repo,FakeDomainRepo()); assert service.create_block(valid_input(),admin)==100; assert repo.created[0]["domain_id"]==7; assert repo.created[0]["horizon_m"]==Decimal("135.5")
def test_viewer_cannot_edit():
    with pytest.raises(PermissionDenied): BlastBlockService(FakeBlockRepo(),FakeDomainRepo()).create_block(valid_input(),viewer)
def test_block_validation_rejects_missing_domain_and_bad_status():
    service=BlastBlockService(FakeBlockRepo(),FakeDomainRepo())
    with pytest.raises(ValidationError): service.create_block(valid_input(domain_id=99),admin)
    with pytest.raises(ValidationError): service.create_block(valid_input(status="bad"),admin)
def test_repository_filters_are_forwarded():
    repo=FakeBlockRepo(); service=BlastBlockService(repo,FakeDomainRepo()); assert service.list_blocks(domain_id=7,status="planned")==[]

def test_block_update_preserves_zero_horizon_and_empty_planned_date():
    repo=FakeBlockRepo(); service=BlastBlockService(repo,FakeDomainRepo())
    service.update_block(5,valid_input(horizon_text="0",planned_blast_date=None),editor,expected_version=0)
    assert repo.updated[0]["horizon_m"] == Decimal("0")
    assert repo.updated[0]["planned_blast_date"] is None

def test_linked_production_block_domain_is_immutable():
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def get(self,model,key):
            if model.__name__ == "BlastBlock": return type("Block",(),{"id":5,"domain_id":7})()
            return FakeDomain(key,site_id=10)
        def scalar(self,_statement): return 44
    class Factory:
        def __call__(self): return Session()
        def begin(self): return Session()
    repo=FakeBlockRepo(); repo.session_factory=Factory()
    domains=FakeDomainRepo(); domains.domains.append(FakeDomain(8,site_id=10)); service=BlastBlockService(repo,domains,audit_repository=object())
    with pytest.raises(ValidationError,match="Moving a Block between Domains"):
        service.update_block(5,valid_input(domain_id=8),editor,expected_version=0)


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


def test_audit_value_formatting_and_changed_fields() -> None:
    from datetime import date
    from decimal import Decimal
    from services.blast_block_service import build_audit_changes, format_audit_value

    assert format_audit_value("status", "planned") == "Запланирован"
    assert format_audit_value("planned_blast_date", date(2026, 7, 15)) == "15.07.2026"
    assert format_audit_value("horizon_m", Decimal("760.5000")) == "760.5"
    changes = build_audit_changes(
        {"block_number": "A", "domain_id": 1, "horizon_m": Decimal("1.0"), "planned_blast_date": None, "status": "planned", "comment": None},
        {"block_number": "A", "domain_id": 2, "horizon_m": Decimal("1.0"), "planned_blast_date": None, "status": "blasted", "comment": None},
        {1: "Old site", 2: "New site"},
    )
    assert changes == [("domain_id", "Old site", "New site"), ("status", "Запланирован", "Взорван")]
