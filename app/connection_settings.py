from __future__ import annotations

import configparser
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL, make_url

from database.env import load_local_env
from database.settings import ConfigurationError, Settings


CONFIG_DIR_OVERRIDE = "SLOPEFORGE_CONFIG_DIR"
CONFIG_FILE_NAME = "connection.ini"


class ConnectionSettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConnectionProfile:
    host: str = "localhost"
    port: int = 5432
    database: str = "slopeforge"
    username: str = ""
    password: str = ""
    storage_root: str | Path = ""

    def normalized(self) -> "ConnectionProfile":
        storage_text = str(self.storage_root).strip()
        return ConnectionProfile(
            host=self.host.strip(),
            port=int(self.port),
            database=self.database.strip(),
            username=self.username.strip(),
            password=self.password,
            storage_root=Path(storage_text).expanduser() if storage_text else "",
        )

    def validate_required(self) -> None:
        missing = []
        if not self.host.strip():
            missing.append("Server / Host")
        if not self.database.strip():
            missing.append("Database")
        if not self.username.strip():
            missing.append("User")
        if not str(self.storage_root).strip():
            missing.append("File storage path")
        if not 1 <= int(self.port) <= 65535:
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
        return Settings.from_values(database_url, profile.storage_root)

    @classmethod
    def from_settings(cls, settings: Settings) -> "ConnectionProfile":
        url = make_url(settings.database_url)
        return cls(
            host=url.host or "localhost",
            port=int(url.port or 5432),
            database=url.database or "",
            username=url.username or "",
            password=url.password or "",
            storage_root=settings.storage_root,
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


class ConnectionSettingsStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_config_directory() / CONFIG_FILE_NAME

    def load(self) -> ConnectionProfile | None:
        if not self.path.is_file():
            return None
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(self.path, encoding="utf-8")
            section = parser["connection"]
            profile = ConnectionProfile(
                host=section.get("host", "localhost"),
                port=section.getint("port", fallback=5432),
                database=section.get("database", "slopeforge"),
                username=section.get("username", ""),
                password=section.get("password", ""),
                storage_root=section.get("storage_root", ""),
            )
            profile.validate_required()
            return profile.normalized()
        except (OSError, KeyError, ValueError, configparser.Error, ConnectionSettingsError) as exc:
            raise ConnectionSettingsError(
                f"Saved connection settings could not be read: {self.path}"
            ) from exc

    def save(self, profile: ConnectionProfile) -> None:
        profile.validate_required()
        profile = profile.normalized()
        parser = configparser.ConfigParser(interpolation=None)
        parser["connection"] = {
            "host": profile.host,
            "port": str(profile.port),
            "database": profile.database,
            "username": profile.username,
            "password": profile.password,
            "storage_root": str(profile.storage_root),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                parser.write(handle)
            os.replace(temporary, self.path)
        except OSError as exc:
            raise ConnectionSettingsError(
                f"Connection settings could not be saved: {self.path}"
            ) from exc


def environment_profile() -> ConnectionProfile | None:
    load_local_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    storage_root = os.getenv("STORAGE_ROOT", "").strip()
    if not database_url or not storage_root:
        return None
    settings = Settings.from_values(database_url, storage_root)
    return ConnectionProfile.from_settings(settings)


def resolve_runtime_settings(
    store: ConnectionSettingsStore | None = None,
) -> tuple[Settings, str]:
    env_profile = environment_profile()
    if env_profile is not None:
        return env_profile.to_settings(), "environment"
    saved = (store or ConnectionSettingsStore()).load()
    if saved is not None:
        return saved.to_settings(), "saved"
    raise ConfigurationError(
        "No PostgreSQL and file-storage configuration has been saved yet."
    )


def effective_profile(
    store: ConnectionSettingsStore | None = None,
) -> tuple[ConnectionProfile | None, str | None]:
    env_profile = environment_profile()
    if env_profile is not None:
        return env_profile, "environment"
    saved = (store or ConnectionSettingsStore()).load()
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
