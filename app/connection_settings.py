from __future__ import annotations

import configparser
import json
import os
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import URL, make_url

from app.credential_store import (
    CredentialStore,
    CredentialStoreError,
    default_credential_store,
)
from database.env import load_local_env
from database.settings import ConfigurationError, Settings


CONFIG_DIR_OVERRIDE = "SLOPEFORGE_CONFIG_DIR"
CONFIG_FILE_NAME = "connections.json"
LEGACY_CONFIG_FILE_NAME = "connection.ini"
PROFILE_STORE_VERSION = 1
FULL_STORAGE = "full"
DATABASE_ONLY = "database_only"
PROFILE_MODES = {FULL_STORAGE, DATABASE_ONLY}


class ConnectionSettingsError(RuntimeError):
    pass


class MissingConnectionConfiguration(ConfigurationError):
    pass


class ConnectionSelectionRequired(MissingConnectionConfiguration):
    pass


@dataclass(frozen=True)
class ConnectionProfile:
    profile_id: str = ""
    name: str = ""
    host: str = "localhost"
    port: int = 5432
    database: str = "slopeforge"
    username: str = ""
    password: str = ""
    mode: str = FULL_STORAGE
    storage_root: str | Path = ""
    last_used_at: str | None = None

    @property
    def storage_available(self) -> bool:
        return self.mode == FULL_STORAGE and bool(str(self.storage_root).strip())

    @property
    def display_name(self) -> str:
        if self.name.strip():
            return self.name.strip()
        return f"{self.host.strip() or 'localhost'} / {self.database.strip() or 'slopeforge'}"

    def normalized(self) -> "ConnectionProfile":
        storage_text = str(self.storage_root or "").strip()
        mode = str(self.mode or FULL_STORAGE).strip().lower()
        if mode not in PROFILE_MODES:
            mode = FULL_STORAGE
        return ConnectionProfile(
            profile_id=self.profile_id.strip(),
            name=self.name.strip(),
            host=self.host.strip(),
            port=int(self.port),
            database=self.database.strip(),
            username=self.username.strip(),
            password=self.password,
            mode=mode,
            storage_root=(
                Path(storage_text).expanduser() if storage_text and mode == FULL_STORAGE else ""
            ),
            last_used_at=self.last_used_at,
        )

    def with_identity(self) -> "ConnectionProfile":
        profile = self.normalized()
        return profile if profile.profile_id else replace(profile, profile_id=str(uuid4()))

    def validate_required(self) -> None:
        profile = self.normalized()
        missing = []
        if not profile.host:
            missing.append("Server / Host")
        if not profile.database:
            missing.append("Database")
        if not profile.username:
            missing.append("User")
        if profile.mode not in PROFILE_MODES:
            raise ConnectionSettingsError("Unknown connection mode.")
        if profile.mode == FULL_STORAGE and not str(profile.storage_root).strip():
            missing.append("File storage path")
        if not 1 <= int(profile.port) <= 65535:
            raise ConnectionSettingsError("Port must be between 1 and 65535.")
        if missing:
            raise ConnectionSettingsError("Required fields: " + ", ".join(missing))

    def to_settings(self) -> Settings:
        self.validate_required()
        profile = self.normalized()
        database_url = URL.create(
            drivername="postgresql+psycopg",
            username=profile.username,
            password=profile.password or None,
            host=profile.host,
            port=profile.port,
            database=profile.database,
        ).render_as_string(hide_password=False)
        return Settings.from_values(
            database_url,
            profile.storage_root if profile.mode == FULL_STORAGE else None,
            database_only=profile.mode == DATABASE_ONLY,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        profile_id: str = "",
        name: str = "",
    ) -> "ConnectionProfile":
        url = make_url(settings.database_url)
        return cls(
            profile_id=profile_id,
            name=name,
            host=url.host or "localhost",
            port=int(url.port or 5432),
            database=url.database or "",
            username=url.username or "",
            password=url.password or "",
            mode=DATABASE_ONLY if settings.storage_root is None else FULL_STORAGE,
            storage_root=settings.storage_root or "",
        )


def default_config_directory() -> Path:
    override = os.getenv(CONFIG_DIR_OVERRIDE, "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.getenv("APPDATA", "").strip()
        if base:
            return Path(base) / "SlopeForge"
    return Path.home() / ".config" / "SlopeForge"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConnectionSettingsStore:
    """Local multi-profile metadata store with secrets delegated to OS credential storage."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        credential_store: CredentialStore | None = None,
        legacy_path: str | Path | None = None,
    ):
        self.path = Path(path) if path is not None else default_config_directory() / CONFIG_FILE_NAME
        self.legacy_path = (
            Path(legacy_path)
            if legacy_path is not None
            else self.path.with_name(LEGACY_CONFIG_FILE_NAME)
        )
        self.credentials = credential_store or default_credential_store()

    def _empty_document(self) -> dict:
        return {
            "version": PROFILE_STORE_VERSION,
            "last_profile_id": None,
            "auto_connect_profile_id": None,
            "profiles": [],
        }

    def _read_document(self) -> dict:
        self._migrate_legacy_if_needed()
        if not self.path.is_file():
            return self._empty_document()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise ConnectionSettingsError(
                f"Saved connection profiles could not be read: {self.path}"
            ) from exc
        if not isinstance(data, dict) or data.get("version") != PROFILE_STORE_VERSION:
            raise ConnectionSettingsError("Saved connection profile format is not supported.")
        if not isinstance(data.get("profiles"), list):
            raise ConnectionSettingsError("Saved connection profile list is invalid.")
        return data

    def _write_document(self, data: dict) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ConnectionSettingsError(
                f"Connection profiles could not be saved: {self.path}"
            ) from exc

    @staticmethod
    def _profile_to_json(profile: ConnectionProfile) -> dict:
        profile = profile.normalized()
        return {
            "id": profile.profile_id,
            "name": profile.display_name,
            "host": profile.host,
            "port": profile.port,
            "database": profile.database,
            "username": profile.username,
            "mode": profile.mode,
            "storage_root": str(profile.storage_root or ""),
            "last_used_at": profile.last_used_at,
        }

    @staticmethod
    def _profile_from_json(value: dict) -> ConnectionProfile:
        try:
            profile = ConnectionProfile(
                profile_id=str(value.get("id") or ""),
                name=str(value.get("name") or ""),
                host=str(value.get("host") or "localhost"),
                port=int(value.get("port") or 5432),
                database=str(value.get("database") or "slopeforge"),
                username=str(value.get("username") or ""),
                mode=str(value.get("mode") or FULL_STORAGE),
                storage_root=str(value.get("storage_root") or ""),
                last_used_at=value.get("last_used_at"),
            ).normalized()
            if not profile.profile_id:
                raise ValueError("Profile id is missing")
            profile.validate_required()
            return profile
        except (TypeError, ValueError, ConnectionSettingsError) as exc:
            raise ConnectionSettingsError("A saved connection profile is invalid.") from exc

    def list_profiles(self) -> list[ConnectionProfile]:
        data = self._read_document()
        profiles = [self._profile_from_json(item) for item in data["profiles"]]
        return sorted(
            profiles,
            key=lambda item: (
                item.profile_id != data.get("last_profile_id"),
                item.display_name.casefold(),
            ),
        )

    def load(self) -> ConnectionProfile | None:
        profiles = self.list_profiles()
        if not profiles:
            return None
        auto_id = self.auto_connect_profile_id()
        if auto_id:
            try:
                return self.runtime_profile(auto_id)
            except KeyError:
                self.set_auto_connect_profile(None)
        if len(profiles) == 1:
            return self.runtime_profile(profiles[0].profile_id)
        return None

    def profile(self, profile_id: str, *, include_password: bool = False) -> ConnectionProfile:
        target = str(profile_id)
        for profile in self.list_profiles():
            if profile.profile_id == target:
                if include_password:
                    try:
                        secret = self.credentials.read(profile.profile_id) or ""
                    except CredentialStoreError as exc:
                        raise ConnectionSettingsError(str(exc)) from exc
                    return replace(profile, password=secret)
                return profile
        raise KeyError(profile_id)

    def runtime_profile(self, profile_id: str) -> ConnectionProfile:
        return self.profile(profile_id, include_password=True)

    def save(self, profile: ConnectionProfile, *, password: str | None = None) -> ConnectionProfile:
        return self.upsert(profile, password=password)

    def upsert(
        self,
        profile: ConnectionProfile,
        *,
        password: str | None = None,
        force_new: bool = False,
    ) -> ConnectionProfile:
        data = self._read_document()
        profile = profile.normalized()
        if not profile.profile_id:
            if not force_new and len(data["profiles"]) == 1:
                profile = replace(
                    profile, profile_id=str(data["profiles"][0].get("id") or "")
                )
            if not profile.profile_id:
                profile = replace(profile, profile_id=str(uuid4()))
        profile.validate_required()
        existing = next(
            (item for item in data["profiles"] if str(item.get("id")) == profile.profile_id),
            None,
        )
        secret_to_write = profile.password if password is None and profile.password else password
        previous_secret: str | None = None
        previous_username = str(existing.get("username") or "") if existing else profile.username
        credential_changed = secret_to_write is not None
        if credential_changed:
            try:
                previous_secret = self.credentials.read(profile.profile_id)
                self.credentials.write(profile.profile_id, profile.username, secret_to_write)
            except CredentialStoreError as exc:
                raise ConnectionSettingsError(str(exc)) from exc

        payload = self._profile_to_json(replace(profile, password=""))
        if existing is None:
            data["profiles"].append(payload)
        else:
            existing.clear()
            existing.update(payload)
        try:
            self._write_document(data)
        except ConnectionSettingsError as save_exc:
            if credential_changed:
                try:
                    if previous_secret is None:
                        self.credentials.delete(profile.profile_id)
                    else:
                        self.credentials.write(
                            profile.profile_id,
                            previous_username,
                            previous_secret,
                        )
                except CredentialStoreError as rollback_exc:
                    raise ConnectionSettingsError(
                        "Connection profile save failed and the database credential could not be restored."
                    ) from rollback_exc
            raise save_exc
        return replace(profile, password=secret_to_write or profile.password or "")

    def remove(self, profile_id: str) -> None:
        data = self._read_document()
        target = str(profile_id)
        existing = next(
            (item for item in data["profiles"] if str(item.get("id")) == target),
            None,
        )
        if existing is None:
            return
        try:
            previous_secret = self.credentials.read(target)
            if previous_secret is not None:
                self.credentials.delete(target)
        except CredentialStoreError as exc:
            raise ConnectionSettingsError(str(exc)) from exc

        data["profiles"] = [
            item for item in data["profiles"] if str(item.get("id")) != target
        ]
        if data.get("last_profile_id") == target:
            data["last_profile_id"] = None
        if data.get("auto_connect_profile_id") == target:
            data["auto_connect_profile_id"] = None
        try:
            self._write_document(data)
        except ConnectionSettingsError as save_exc:
            if previous_secret is not None:
                try:
                    self.credentials.write(
                        target,
                        str(existing.get("username") or ""),
                        previous_secret,
                    )
                except CredentialStoreError as rollback_exc:
                    raise ConnectionSettingsError(
                        "Connection removal failed and the database credential could not be restored."
                    ) from rollback_exc
            raise save_exc

    def last_profile_id(self) -> str | None:
        value = self._read_document().get("last_profile_id")
        return str(value) if value else None

    def mark_used(self, profile_id: str) -> None:
        data = self._read_document()
        target = str(profile_id)
        found = False
        for item in data["profiles"]:
            if str(item.get("id")) == target:
                item["last_used_at"] = _now_iso()
                found = True
                break
        if not found:
            raise KeyError(profile_id)
        data["last_profile_id"] = target
        self._write_document(data)

    def auto_connect_profile_id(self) -> str | None:
        value = self._read_document().get("auto_connect_profile_id")
        return str(value) if value else None

    def set_auto_connect_profile(self, profile_id: str | None) -> None:
        data = self._read_document()
        target = str(profile_id) if profile_id else None
        if target and not any(str(item.get("id")) == target for item in data["profiles"]):
            raise KeyError(profile_id)
        data["auto_connect_profile_id"] = target
        self._write_document(data)

    def _migrate_legacy_if_needed(self) -> None:
        if self.path.exists() or not self.legacy_path.is_file():
            return
        parser = configparser.ConfigParser(interpolation=None)
        credential_written = False
        profile_id = ""
        try:
            parser.read(self.legacy_path, encoding="utf-8")
            section = parser["connection"]
            profile = ConnectionProfile(
                profile_id=str(uuid4()),
                name="Local SlopeForge",
                host=section.get("host", "localhost"),
                port=section.getint("port", fallback=5432),
                database=section.get("database", "slopeforge"),
                username=section.get("username", ""),
                mode=FULL_STORAGE,
                storage_root=section.get("storage_root", ""),
            ).normalized()
            profile.validate_required()
            profile_id = profile.profile_id
            password = section.get("password", "")
            if password:
                self.credentials.write(profile.profile_id, profile.username, password)
                credential_written = True
            data = self._empty_document()
            data["profiles"] = [self._profile_to_json(profile)]
            data["last_profile_id"] = profile.profile_id
            # Migration must not silently opt the user into skipping the new
            # startup selector. Auto-connect is an explicit local preference.
            data["auto_connect_profile_id"] = None
            self._write_document(data)
            # The legacy INI contains the PostgreSQL password in plaintext.
            # Once both the credential and metadata are safely persisted, remove
            # the old file instead of renaming it and retaining the secret.
            self.legacy_path.unlink()
        except (
            OSError,
            KeyError,
            ValueError,
            configparser.Error,
            ConnectionSettingsError,
            CredentialStoreError,
        ) as exc:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass
            if credential_written and profile_id:
                try:
                    self.credentials.delete(profile_id)
                except CredentialStoreError:
                    pass
            raise ConnectionSettingsError(
                f"Legacy connection settings could not be migrated: {self.legacy_path}"
            ) from exc


def environment_settings() -> Settings | None:
    load_local_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None
    storage_root = os.getenv("STORAGE_ROOT", "").strip()
    database_only = not bool(storage_root)
    return Settings.from_values(
        database_url,
        storage_root or None,
        database_only=database_only,
    )


def environment_profile() -> ConnectionProfile | None:
    settings = environment_settings()
    if settings is None:
        return None
    return ConnectionProfile.from_settings(
        settings,
        profile_id="environment",
        name="Environment connection",
    )


def resolve_runtime_settings(
    store: ConnectionSettingsStore | None = None,
    *,
    profile_id: str | None = None,
) -> tuple[Settings, str]:
    env_settings = environment_settings()
    if env_settings is not None:
        return env_settings, "environment"
    store = store or ConnectionSettingsStore()
    if profile_id:
        return store.runtime_profile(profile_id).to_settings(), "saved"
    saved = store.load()
    if saved is not None:
        return saved.to_settings(), "saved"
    if store.list_profiles():
        raise ConnectionSelectionRequired(
            "Multiple PostgreSQL connections are saved. Select a server in SlopeForge."
        )
    raise MissingConnectionConfiguration(
        "No PostgreSQL connection profile has been saved yet."
    )


def effective_profile(
    store: ConnectionSettingsStore | None = None,
) -> tuple[ConnectionProfile | None, str | None]:
    env_profile = environment_profile()
    if env_profile is not None:
        return env_profile, "environment"
    store = store or ConnectionSettingsStore()
    saved = store.load()
    return (saved, "saved") if saved is not None else (None, None)


def validate_storage_root(path: str | Path) -> Path:
    text = str(path).strip()
    if not text:
        raise ConnectionSettingsError("File storage path is required.")
    root = Path(text).expanduser()
    if not root.exists():
        raise ConnectionSettingsError("The file storage folder does not exist.")
    if not root.is_dir():
        raise ConnectionSettingsError("The file storage path must be a folder.")
    probe_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".slopeforge-write-test-", dir=root, delete=False
        ) as probe:
            probe_path = Path(probe.name)
            probe.write(b"SlopeForge")
    except OSError as exc:
        raise ConnectionSettingsError(
            "The file storage folder is not writable."
        ) from exc
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink(missing_ok=True)
            except OSError:
                pass
    return root
