from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from application.dto.current_user import CurrentUser


@dataclass(frozen=True)
class AppContext:
    session_factory: Callable[[], Any]
    current_user: CurrentUser
    storage_root: Path
