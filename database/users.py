from __future__ import annotations

<<<<<<< HEAD
from datetime import datetime, timezone

=======
>>>>>>> origin/main
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .models import User
from .security import hash_password

FIRST_ADMIN_LOCK_KEY = "slopeforge:first_admin"


class FirstAdminAlreadyExistsError(RuntimeError):
    pass


def create_user(session: Session, username: str, password: str, full_name: str | None = None, role: str | None = None) -> User:
    existing_count = session.scalar(select(func.count(User.id))) or 0
    assigned_role = "admin" if existing_count == 0 else (role or "viewer")
<<<<<<< HEAD
    user = User(username=username, password_hash=hash_password(password), full_name=full_name or None, role=assigned_role, password_changed_at=datetime.now(timezone.utc), must_change_password=False)
=======
    user = User(username=username, password_hash=hash_password(password), full_name=full_name or None, role=assigned_role)
>>>>>>> origin/main
    session.add(user)
    session.flush()
    return user


def create_first_admin_with_lock(session: Session, username: str, password: str, full_name: str | None = None) -> User:
    """Create the first admin safely using PostgreSQL advisory locking."""
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"), {"lock_key": FIRST_ADMIN_LOCK_KEY})
    existing_count = session.scalar(select(func.count(User.id))) or 0
    if existing_count > 0:
        raise FirstAdminAlreadyExistsError("The first administrator already exists. Sign in with an existing user.")
<<<<<<< HEAD
    user = User(username=username, password_hash=hash_password(password), full_name=full_name or None, role="admin", password_changed_at=datetime.now(timezone.utc), must_change_password=False)
=======
    user = User(username=username, password_hash=hash_password(password), full_name=full_name or None, role="admin")
>>>>>>> origin/main
    session.add(user)
    session.flush()
    return user
