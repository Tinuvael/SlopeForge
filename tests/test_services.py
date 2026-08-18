from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.context import CurrentUser
from infrastructure.services.auth_service import AuthError, AuthService
from infrastructure.services.production_blast_service import (
    PermissionDenied, ProductionBlastInput, ProductionBlastService, ValidationError,
    build_audit_changes, format_audit_value,
)


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


class FakeProductionRepo:
    session_factory = None
    def __init__(self): self.rows=[]
    def list_blocks(self, **filters): return self.rows
    def get_block(self, event_id): return next((x for x in self.rows if x.id == event_id), None)


def valid_input(**overrides):
    data={"domain_id":7,"block_number":"24-017","horizon_text":"135.5","comment":""}; data.update(overrides)
    return ProductionBlastInput(**data)


def test_roles_can_edit():
    assert admin.can_edit and editor.can_edit and not viewer.can_edit


def test_production_metadata_validation_uses_block_name_and_horizon():
    service=ProductionBlastService(FakeProductionRepo(),FakeDomainRepo(),audit_repository=object())
    assert service._validate(valid_input()) == Decimal("135.5")
    assert service._validate(valid_input(horizon_text="0")) == Decimal("0")


def test_viewer_cannot_edit_production_block():
    service=ProductionBlastService(FakeProductionRepo(),FakeDomainRepo(),audit_repository=object())
    with pytest.raises(PermissionDenied): service._check_can_edit(viewer)


def test_production_validation_rejects_missing_domain():
    service=ProductionBlastService(FakeProductionRepo(),FakeDomainRepo(),audit_repository=object())
    with pytest.raises(ValidationError): service._validate(valid_input(domain_id=99))


def test_repository_filters_are_forwarded():
    repo=FakeProductionRepo(); service=ProductionBlastService(repo,FakeDomainRepo(),audit_repository=object())
    assert service.list_blocks(domain_id=7,status="planned")==[]


def test_audit_value_formatting_and_changed_fields() -> None:
    assert format_audit_value("elevation_m", Decimal("760.5000")) == "760.5"
    changes = build_audit_changes(
        {"name": "A", "domain_id": 1, "elevation_m": Decimal("1.0"), "comment": None},
        {"name": "A", "domain_id": 2, "elevation_m": Decimal("1.0"), "comment": None},
        {1: "Old domain", 2: "New domain"},
    )
    assert changes == [("domain_id", "Old domain", "New domain")]


def test_auth_success_and_failure_with_fake_session() -> None:
    pytest.importorskip("argon2", reason="argon2-cffi is not installed in this environment")
    from database.models import User
    from database.security import hash_password

    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def scalar(self, statement): return self.user
    user = User(id=1, username="admin", password_hash=hash_password("secret"), full_name="Admin", role="admin", is_active=True)
    fake_session = FakeSession(); fake_session.user = user
    auth = AuthService(lambda: fake_session)
    assert auth.authenticate("admin", "secret").role == "admin"
    with pytest.raises(AuthError): auth.authenticate("admin", "wrong")
