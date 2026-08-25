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

from application.dto.current_user import CurrentUser
from database.models import RememberToken, User

REMEMBER_DAYS = 90


@dataclass(frozen=True)
class RememberedSession:
    current_user: CurrentUser
    token_hash: str


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _config_directory() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "SlopeForge"
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(base or Path.home() / ".config" / "SlopeForge")


def _scope_filename(scope_id: str) -> str:
    digest = hashlib.sha256(str(scope_id).encode("utf-8")).hexdigest()[:24]
    return f"{digest}.json"


def legacy_session_file_path() -> Path:
    return _config_directory() / "session.json"


def session_file_path(scope_id: str | None = None) -> Path:
    if scope_id is None:
        return legacy_session_file_path()
    return _config_directory() / "sessions" / _scope_filename(scope_id)


def load_local_session(scope_id: str | None = None) -> dict | None:
    path = session_file_path(scope_id)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        clear_local_session(scope_id)
        return None


def save_local_session(
    username: str,
    token: str,
    device_name: str,
    expires_at: datetime,
    *,
    scope_id: str | None = None,
) -> None:
    path = session_file_path(scope_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(
                {
                    "username": username,
                    "token": token,
                    "device_name": device_name,
                    "expires_at": expires_at.isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        # A failed atomic replace must not leave the raw remember token behind in
        # a plaintext temporary file.
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass


def clear_local_session(scope_id: str | None = None) -> None:
    try:
        session_file_path(scope_id).unlink(missing_ok=True)
    except Exception:
        pass


def default_device_name() -> str:
    return platform.node() or "This computer"


class RememberTokenService:
    def __init__(
        self,
        session_factory,
        *,
        scope_id: str = "default",
        migrate_legacy: bool = False,
    ):
        self.session_factory = session_factory
        self.scope_id = str(scope_id or "default")
        self.migrate_legacy = bool(migrate_legacy)

    def _revoke_created_token(self, hashed: str) -> None:
        """Compensate a committed token when its local secret cannot be persisted."""
        with self.session_factory() as session:
            try:
                remember = session.scalar(
                    select(RememberToken).where(RememberToken.token_hash == hashed)
                )
                if remember is not None and remember.revoked_at is None:
                    remember.revoked_at = datetime.now(timezone.utc)
                    session.commit()
            except Exception:
                session.rollback()
                raise

    def create_for_user(
        self,
        user_id: int,
        username: str,
        device_name: str | None = None,
    ) -> str:
        raw_token = secrets.token_urlsafe(48)
        hashed = token_hash(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REMEMBER_DAYS)
        device = device_name or default_device_name()
        with self.session_factory() as session:
            try:
                session.add(
                    RememberToken(
                        user_id=user_id,
                        token_hash=hashed,
                        device_name=device,
                        expires_at=expires_at,
                    )
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

        try:
            save_local_session(
                username,
                raw_token,
                device,
                expires_at,
                scope_id=self.scope_id,
            )
        except Exception as local_exc:
            try:
                self._revoke_created_token(hashed)
            except Exception as cleanup_exc:
                raise RuntimeError(
                    "Remembered sign-in could not be saved locally, and its server token could not be revoked."
                ) from cleanup_exc
            raise local_exc
        return raw_token

    def _authenticate_data(self, data: dict | None) -> RememberedSession | None:
        if not data or not data.get("token"):
            return None
        hashed = token_hash(str(data["token"]))
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            remember = session.scalar(
                select(RememberToken).where(RememberToken.token_hash == hashed)
            )
            if (
                remember is None
                or remember.revoked_at is not None
                or remember.expires_at <= now
                or remember.user is None
                or not remember.user.is_active
            ):
                return None
            remember.last_used_at = now
            remember.user.last_login_at = now
            session.commit()
            user = remember.user
            return RememberedSession(
                CurrentUser(user.id, user.username, user.full_name, user.role),
                hashed,
            )

    def authenticate_local(self) -> RememberedSession | None:
        data = load_local_session(self.scope_id)
        remembered = self._authenticate_data(data)
        if remembered is not None:
            return remembered
        if data is not None:
            clear_local_session(self.scope_id)

        if not self.migrate_legacy:
            return None
        legacy = load_local_session(None)
        remembered = self._authenticate_data(legacy)
        if remembered is None:
            return None
        try:
            expires_text = str(legacy.get("expires_at") or "")
            expires_at = datetime.fromisoformat(expires_text)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            save_local_session(
                str(legacy.get("username") or remembered.current_user.username),
                str(legacy["token"]),
                str(legacy.get("device_name") or default_device_name()),
                expires_at,
                scope_id=self.scope_id,
            )
            clear_local_session(None)
        except Exception:
            # Authentication already succeeded. Failure to migrate the local file
            # must not invalidate the server token or block sign-in.
            pass
        return remembered

    def revoke_local(self) -> None:
        data = load_local_session(self.scope_id)
        if data and data.get("token"):
            self.revoke_hash(token_hash(str(data["token"])))
        clear_local_session(self.scope_id)

    def forget_local(self) -> None:
        self.revoke_local()

    def revoke_hash(self, hashed: str) -> None:
        with self.session_factory() as session:
            remember = session.scalar(
                select(RememberToken).where(RememberToken.token_hash == hashed)
            )
            if remember and remember.revoked_at is None:
                remember.revoked_at = datetime.now(timezone.utc)
                session.commit()

    def revoke_all_for_user(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            for remember in session.scalars(
                select(RememberToken).where(
                    RememberToken.user_id == user_id,
                    RememberToken.revoked_at.is_(None),
                )
            ):
                remember.revoked_at = now
            session.commit()
