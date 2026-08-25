from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from sqlalchemy.engine import make_url

from database.settings import Settings


class PostgresBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupArtifact:
    path: Path
    size_bytes: int
    created_at: datetime


Runner = Callable[..., subprocess.CompletedProcess]
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def _filename_component(value: str | None, fallback: str) -> str:
    cleaned = _SAFE_COMPONENT.sub("_", str(value or "").strip()).strip("._-")
    return cleaned or fallback


def _redact(text: str, secret: str | None) -> str:
    rendered = str(text or "")
    if not secret:
        return rendered
    for candidate in {secret, quote(secret, safe=""), quote(secret, safe="/@")}:
        if candidate:
            rendered = rendered.replace(candidate, "<redacted>")
    return rendered


def resolve_pg_dump_executable(explicit: str | None = None) -> str:
    """Resolve pg_dump without persisting a machine-specific executable path."""
    candidate = str(explicit or os.getenv("SLOPEFORGE_PG_DUMP", "")).strip()
    if candidate:
        return candidate
    discovered = shutil.which("pg_dump")
    if discovered:
        return discovered
    if os.name == "nt":
        program_files = Path(os.getenv("ProgramFiles", r"C:\Program Files"))
        postgres_root = program_files / "PostgreSQL"
        if postgres_root.is_dir():
            installations = sorted(
                (path for path in postgres_root.iterdir() if path.is_dir()),
                key=lambda path: path.name,
                reverse=True,
            )
            for installation in installations:
                executable = installation / "bin" / "pg_dump.exe"
                if executable.is_file():
                    return str(executable)
    raise PostgresBackupError(
        "pg_dump was not found. Install PostgreSQL client tools or set SLOPEFORGE_PG_DUMP."
    )


def _pg_environment(settings: Settings) -> tuple[dict[str, str], str | None]:
    url = make_url(settings.database_url)
    env = os.environ.copy()
    if url.host:
        env["PGHOST"] = str(url.host)
    if url.port:
        env["PGPORT"] = str(url.port)
    if url.database:
        env["PGDATABASE"] = str(url.database)
    if url.username:
        env["PGUSER"] = str(url.username)
    password = str(url.password) if url.password is not None else None
    if password is not None:
        env["PGPASSWORD"] = password

    query_to_env = {
        "connect_timeout": "PGCONNECT_TIMEOUT",
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
        "application_name": "PGAPPNAME",
    }
    for key, env_name in query_to_env.items():
        value = url.query.get(key)
        if value is not None:
            env[env_name] = str(value)
    return env, password


def backup_filename(
    settings: Settings,
    revision: str | None,
    created_at: datetime,
) -> str:
    url = make_url(settings.database_url)
    database = _filename_component(url.database, "database")
    revision_part = _filename_component(revision, "unknown")
    stamp = created_at.astimezone(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return f"SlopeForge_{database}_{stamp}_{revision_part}.dump"


def create_postgres_backup(
    settings: Settings,
    backup_directory: str | Path,
    *,
    revision: str | None,
    pg_dump_executable: str | None = None,
    now: Callable[[], datetime] | None = None,
    runner: Runner = subprocess.run,
) -> BackupArtifact:
    """Create and verify a custom-format PostgreSQL backup without exposing secrets."""
    created_at = (now or (lambda: datetime.now(timezone.utc)))()
    directory = Path(backup_directory).expanduser()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PostgresBackupError(
            f"Could not create the backup directory: {directory}"
        ) from exc

    target = directory / backup_filename(settings, revision, created_at)
    if target.exists():
        raise PostgresBackupError(
            f"Backup already exists and will not be overwritten: {target}"
        )

    executable = resolve_pg_dump_executable(pg_dump_executable)
    env, password = _pg_environment(settings)
    command = [
        executable,
        "--format=custom",
        "--no-password",
        "--file",
        str(target),
    ]
    try:
        result = runner(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PostgresBackupError(
            "pg_dump could not be started. Check the configured PostgreSQL client tools path."
        ) from exc
    except OSError as exc:
        raise PostgresBackupError("Could not start pg_dump.") from exc

    if result.returncode != 0:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        stderr = _redact(getattr(result, "stderr", ""), password).strip()
        detail = f" Details: {stderr}" if stderr else ""
        raise PostgresBackupError(
            f"pg_dump failed with exit code {result.returncode}.{detail}"
        )

    try:
        size = target.stat().st_size
    except OSError as exc:
        raise PostgresBackupError(
            "pg_dump reported success but the backup file could not be verified."
        ) from exc
    if size <= 0:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise PostgresBackupError(
            "pg_dump reported success but produced an empty backup file."
        )

    return BackupArtifact(path=target, size_bytes=size, created_at=created_at)
