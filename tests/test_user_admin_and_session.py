from __future__ import annotations

from services.session_service import token_hash
from services.user_admin_service import UserAdminPermissionError, UserAdminService
from database.app_context import CurrentUser


def test_remember_token_hash_does_not_store_plain_token() -> None:
    raw = "plain-token"
    hashed = token_hash(raw)
    assert hashed != raw
    assert len(hashed) == 64
    assert token_hash(raw) == hashed


def test_user_admin_requires_admin_role() -> None:
    service = UserAdminService(lambda: None)
    viewer = CurrentUser(1, "viewer", None, "viewer")
    try:
        service.list_users(viewer)
    except UserAdminPermissionError:
        pass
    else:
        raise AssertionError("viewer must not manage users")
