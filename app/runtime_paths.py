from __future__ import annotations

import os
import sys
from pathlib import Path


def runtime_log_path() -> Path:
    """Return a writable, per-user path for the application log."""
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "SlopeForge" / "logs" / "slopeforge.log"
    return Path.home() / ".local" / "state" / "SlopeForge" / "logs" / "slopeforge.log"
