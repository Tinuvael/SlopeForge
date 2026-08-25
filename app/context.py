from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from application.dto.current_user import CurrentUser


@dataclass(frozen=True)
class AppContext:
    session_factory: Callable[[], Any]
    current_user: CurrentUser
    storage_root: Path | None
    connection_profile_id: str = ""
    connection_profile_name: str = ""
    connection_mode: str = "full"
    session_scope_id: str = ""
    runtime_control: Any | None = None

    @property
    def file_storage_available(self) -> bool:
        return self.storage_root is not None and self.connection_mode != "database_only"
