from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from database.app_context import CurrentUser
from database.models import User
from database.security import hash_password
from services.session_service import RememberTokenService

ROLES = {"admin", "editor", "viewer"}


class UserAdminError(ValueError):
    pass


class UserAdminPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class UserAdminRow:
    id: int
    username: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    created_by: str | None
    updated_by: str | None
    must_change_password: bool


class UserAdminService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.tokens = RememberTokenService(session_factory)

    def _require_admin(self, actor: CurrentUser) -> None:
        if actor.role != "admin":
            raise UserAdminPermissionError("Only administrators can manage users")

    def list_users(self, actor: CurrentUser) -> list[UserAdminRow]:
        self._require_admin(actor)
        with self.session_factory() as session:
            users = list(session.scalars(select(User).order_by(User.username.asc())))
            names = {user.id: user.full_name or user.username for user in users}
            return [UserAdminRow(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
                created_by=names.get(user.created_by_user_id),
                updated_by=names.get(user.updated_by_user_id),
                must_change_password=user.must_change_password,
            ) for user in users]

    def create_user(self, actor: CurrentUser, username: str, full_name: str | None, role: str, password: str, repeat_password: str, is_active: bool = True, must_change_password: bool = False) -> int:
        self._require_admin(actor)
        if not username.strip():
            raise UserAdminError("Username is required")
        if role not in ROLES:
            raise UserAdminError("Invalid role")
        if not password:
            raise UserAdminError("Password is required")
        if password != repeat_password:
            raise UserAdminError("Passwords do not match")
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            try:
                user = User(
                    username=username.strip(),
                    full_name=full_name or None,
                    role=role,
                    password_hash=hash_password(password),
                    is_active=is_active,
                    must_change_password=must_change_password,
                    password_changed_at=now,
                    created_by_user_id=actor.id,
                    updated_by_user_id=actor.id,
                )
                session.add(user)
                session.commit()
                return user.id
            except IntegrityError as exc:
                session.rollback()
                raise UserAdminError("Username already exists") from exc
            except Exception:
                session.rollback()
                raise

    def update_user(self, actor: CurrentUser, user_id: int, full_name: str | None, role: str, is_active: bool, must_change_password: bool) -> None:
        self._require_admin(actor)
        if role not in ROLES:
            raise UserAdminError("Invalid role")
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                raise UserAdminError("User not found")
            user.full_name = full_name or None
            user.role = role
            user.is_active = is_active
            user.must_change_password = must_change_password
            user.updated_by_user_id = actor.id
            session.commit()

    def change_password(self, actor: CurrentUser, user_id: int, password: str, repeat_password: str, must_change_password: bool = False) -> None:
        self._require_admin(actor)
        if not password:
            raise UserAdminError("Password is required")
        if password != repeat_password:
            raise UserAdminError("Passwords do not match")
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                raise UserAdminError("User not found")
            user.password_hash = hash_password(password)
            user.password_changed_at = datetime.now(timezone.utc)
            user.must_change_password = must_change_password
            user.updated_by_user_id = actor.id
            session.commit()

    def set_active(self, actor: CurrentUser, user_id: int, is_active: bool) -> None:
        self._require_admin(actor)
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                raise UserAdminError("User not found")
            user.is_active = is_active
            user.updated_by_user_id = actor.id
            session.commit()

    def revoke_all_sessions(self, actor: CurrentUser, user_id: int) -> None:
        self._require_admin(actor)
        self.tokens.revoke_all_for_user(user_id)
