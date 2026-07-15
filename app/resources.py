from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def application_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parent.parent


def resource_path(relative_path: str | Path) -> Path | None:
    path = application_root() / Path(relative_path)
    if not path.exists():
        logger.warning("Resource not found: %s", path)
        return None
    return path
