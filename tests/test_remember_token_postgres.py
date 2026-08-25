from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import infrastructure.services.session_service as session_service
from database.models import RememberToken, User
from infrastructure.services.session_service import RememberTokenService
from tests.postgres_test_database import is_disposable_test_database

pytestmark = pytest.mark.postgres

URL = os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)
if not is_disposable_test_database(URL):
    pytest.fail("Refusing remember-token tests outside a test database", pytrace=False)


@pytest.fixture
def factory():
    engine = create_engine(URL)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()


def test_failed_local_remember_write_leaves_no_active_server_token(monkeypatch, factory):
    with factory.begin() as session:
        user = User(
            username="remember-user",
            password_hash="hash",
            full_name="Remember User",
            role="viewer",
            is_active=True,
        )
        session.add(user)
        session.flush()
        user_id = user.id

    service = RememberTokenService(factory, scope_id="profile-a")
    monkeypatch.setattr(
        session_service,
        "save_local_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        service.create_for_user(user_id, "remember-user", "workstation")

    with factory() as session:
        all_tokens = session.scalars(
            select(RememberToken).where(RememberToken.user_id == user_id)
        ).all()
        active_count = session.scalar(
            select(func.count(RememberToken.id)).where(
                RememberToken.user_id == user_id,
                RememberToken.revoked_at.is_(None),
            )
        )

    assert len(all_tokens) == 1
    assert all_tokens[0].revoked_at is not None
    assert active_count == 0
