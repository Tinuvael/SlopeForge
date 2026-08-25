from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Protocol


CREDENTIAL_PREFIX = "SlopeForge/PostgreSQL/"


class CredentialStoreError(RuntimeError):
    pass


class CredentialStore(Protocol):
    def read(self, profile_id: str) -> str | None: ...
    def write(self, profile_id: str, username: str, password: str) -> None: ...
    def delete(self, profile_id: str) -> None: ...


def credential_target(profile_id: str) -> str:
    return f"{CREDENTIAL_PREFIX}{str(profile_id).strip()}"


class WindowsCredentialStore:
    """Store PostgreSQL passwords in Windows Credential Manager."""

    @staticmethod
    def _module():
        if sys.platform != "win32":
            raise CredentialStoreError("Windows Credential Manager is unavailable on this platform.")
        try:
            import win32cred
        except ImportError as exc:  # pragma: no cover - Windows packaging guard
            raise CredentialStoreError("Windows Credential Manager support is not installed.") from exc
        return win32cred

    def read(self, profile_id: str) -> str | None:
        win32cred = self._module()
        try:
            result = win32cred.CredRead(
                credential_target(profile_id), win32cred.CRED_TYPE_GENERIC, 0
            )
        except Exception as exc:
            not_found = getattr(win32cred, "ERROR_NOT_FOUND", 1168)
            if getattr(exc, "winerror", None) == not_found or (
                getattr(exc, "args", ()) and exc.args[0] == not_found
            ):
                return None
            raise CredentialStoreError("Could not read the saved database credential.") from exc
        blob = result.get("CredentialBlob", b"")
        if isinstance(blob, bytes):
            if not blob:
                return ""
            for encoding in ("utf-16-le", "utf-8"):
                try:
                    return blob.decode(encoding).rstrip("\x00")
                except UnicodeDecodeError:
                    continue
            return blob.decode(errors="replace").rstrip("\x00")
        return str(blob)

    def write(self, profile_id: str, username: str, password: str) -> None:
        win32cred = self._module()
        # CRED_TYPE_GENERIC treats the credential blob as opaque bytes. UTF-16LE
        # gives deterministic Windows round-tripping without serializing the
        # PostgreSQL password into SlopeForge's profile metadata.
        secret = str(password or "").encode("utf-16-le")
        try:
            win32cred.CredWrite(
                {
                    "Type": win32cred.CRED_TYPE_GENERIC,
                    "TargetName": credential_target(profile_id),
                    "UserName": str(username or ""),
                    "CredentialBlob": secret,
                    "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                    "Comment": "SlopeForge PostgreSQL connection credential",
                },
                0,
            )
        except Exception as exc:
            raise CredentialStoreError("Could not save the database credential.") from exc

    def delete(self, profile_id: str) -> None:
        win32cred = self._module()
        try:
            win32cred.CredDelete(
                credential_target(profile_id), win32cred.CRED_TYPE_GENERIC, 0
            )
        except Exception as exc:
            not_found = getattr(win32cred, "ERROR_NOT_FOUND", 1168)
            if getattr(exc, "winerror", None) == not_found or (
                getattr(exc, "args", ()) and exc.args[0] == not_found
            ):
                return
            raise CredentialStoreError("Could not remove the saved database credential.") from exc


class SessionOnlyCredentialStore:
    """Non-Windows fallback: secrets live only for this process and are never written."""

    def __init__(self):
        self._values: dict[str, str] = {}

    def read(self, profile_id: str) -> str | None:
        return self._values.get(str(profile_id))

    def write(self, profile_id: str, username: str, password: str) -> None:
        del username
        self._values[str(profile_id)] = str(password or "")

    def delete(self, profile_id: str) -> None:
        self._values.pop(str(profile_id), None)


@dataclass
class MemoryCredentialStore:
    """Deterministic credential backend for tests."""

    values: dict[str, str] = field(default_factory=dict)

    def read(self, profile_id: str) -> str | None:
        return self.values.get(str(profile_id))

    def write(self, profile_id: str, username: str, password: str) -> None:
        del username
        self.values[str(profile_id)] = str(password or "")

    def delete(self, profile_id: str) -> None:
        self.values.pop(str(profile_id), None)


def default_credential_store() -> CredentialStore:
    if sys.platform == "win32":
        return WindowsCredentialStore()
    return SessionOnlyCredentialStore()