from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.app_context import CurrentUser
from database.models import RememberToken, User

REMEMBER_DAYS = 90


@dataclass(frozen=True)
class RememberedSession:
    current_user: CurrentUser
    token_hash: str


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_file_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "SlopeForge" / "session.json"
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(base or Path.home() / ".config" / "SlopeForge") / "session.json"


def load_local_session() -> dict | None:
    path = session_file_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        clear_local_session()
        return None


def save_local_session(username: str, token: str, device_name: str, expires_at: datetime) -> None:
    path = session_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "username": username,
        "token": token,
        "device_name": device_name,
        "expires_at": expires_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_local_session() -> None:
    try:
        session_file_path().unlink(missing_ok=True)
    except Exception:
        pass


def default_device_name() -> str:
    return platform.node() or "This computer"


class RememberTokenService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create_for_user(self, user_id: int, username: str, device_name: str | None = None) -> str:
        raw_token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REMEMBER_DAYS)
        with self.session_factory() as session:
            try:
                session.add(RememberToken(user_id=user_id, token_hash=token_hash(raw_token), device_name=device_name or default_device_name(), expires_at=expires_at))
                session.commit()
                save_local_session(username, raw_token, device_name or default_device_name(), expires_at)
                return raw_token
            except Exception:
                session.rollback()
                raise

    def authenticate_local(self) -> RememberedSession | None:
        data = load_local_session()
        if not data or not data.get("token"):
            return None
        hashed = token_hash(data["token"])
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            remember = session.scalar(select(RememberToken).where(RememberToken.token_hash == hashed))
            if remember is None or remember.revoked_at is not None or remember.expires_at <= now or remember.user is None or not remember.user.is_active:
                clear_local_session()
                return None
            remember.last_used_at = now
            remember.user.last_login_at = now
            session.commit()
            user = remember.user
            return RememberedSession(CurrentUser(user.id, user.username, user.full_name, user.role), hashed)

    def revoke_local(self) -> None:
        data = load_local_session()
        if data and data.get("token"):
            self.revoke_hash(token_hash(data["token"]))
        clear_local_session()

    def revoke_hash(self, hashed: str) -> None:
        with self.session_factory() as session:
            remember = session.scalar(select(RememberToken).where(RememberToken.token_hash == hashed))
            if remember and remember.revoked_at is None:
                remember.revoked_at = datetime.now(timezone.utc)
                session.commit()

    def revoke_all_for_user(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            for remember in session.scalars(select(RememberToken).where(RememberToken.user_id == user_id, RememberToken.revoked_at.is_(None))):
                remember.revoked_at = now
            session.commit()
