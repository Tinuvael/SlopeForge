from __future__ import annotations

from collections.abc import Callable
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.app_context import CurrentUser
from database.models import User


class AuthError(ValueError):
    pass


class AuthService:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def has_users(self) -> bool:
        with self.session_factory() as session:
            return (session.scalar(select(func.count(User.id))) or 0) > 0

    def create_first_admin(self, username: str, full_name: str | None, password: str) -> CurrentUser:
        with self.session_factory() as session:
            try:
                from database.users import FirstAdminAlreadyExistsError, create_first_admin_with_lock
                try:
                    user = create_first_admin_with_lock(session, username=username.strip(), password=password, full_name=full_name)
                except FirstAdminAlreadyExistsError as exc:
                    raise AuthError(str(exc)) from exc
                session.commit()
                return CurrentUser(id=user.id, username=user.username, full_name=user.full_name, role=user.role)
            except Exception:
                session.rollback()
                raise

    def authenticate(self, username: str, password: str) -> CurrentUser:
        with self.session_factory() as session:
            user = session.scalar(select(User).where(User.username == username.strip(), User.is_active.is_(True)))
            from database.security import verify_password
            if user is None or not verify_password(password, user.password_hash):
                raise AuthError("Invalid username or password")
            return CurrentUser(id=user.id, username=user.username, full_name=user.full_name, role=user.role)
