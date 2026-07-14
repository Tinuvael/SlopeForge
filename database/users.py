from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import User
from .security import hash_password


def create_user(session: Session, username: str, password: str, full_name: str | None = None, role: str | None = None) -> User:
    existing_count = session.scalar(select(func.count(User.id))) or 0
    assigned_role = "admin" if existing_count == 0 else (role or "viewer")
    user = User(username=username, password_hash=hash_password(password), full_name=full_name or None, role=assigned_role)
    session.add(user)
    session.flush()
    return user
