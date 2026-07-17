from __future__ import annotations

from collections.abc import Callable
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import User


class UserRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def count_users(self) -> int:
        with self.session_factory() as session:
            return session.scalar(select(func.count(User.id))) or 0

    def get_by_username(self, username: str) -> User | None:
        with self.session_factory() as session:
            user = session.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
            if user:
                session.expunge(user)
            return user
