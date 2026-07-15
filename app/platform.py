from __future__ import annotations

import ctypes
import logging
import sys

from .config import APP_USER_MODEL_ID

logger = logging.getLogger(__name__)


def set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        logger.exception("Failed to set Windows AppUserModelID")
